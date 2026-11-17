'use strict';
const $ = (selector, root = document) => root.querySelector(selector);
const statusNames = {to_read: 'To read', reading: 'Reading', read: 'Read'};
const drafts = new Map();
let busy = false;

function message(text, error = false) {
  $('#message').textContent = text;
  $('#message').classList.toggle('error', error);
}
function setBusy(value) {
  busy = value;
  document.querySelectorAll('button, input, textarea, select').forEach(control => { control.disabled = value; });
}
async function request(path, method = 'GET', data) {
  let response;
  try {
    response = await fetch(path, {method, headers: {'Content-Type': 'application/json'}, ...(data === undefined ? {} : {body: JSON.stringify(data)})});
  } catch {
    throw new Error('Connection lost. Your changes may have reached the server. Refresh to check saved data; your draft is retained.');
  }
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'The request could not be completed.');
  return result;
}
async function action(work) {
  if (busy) return;
  setBusy(true);
  try { await work(); } catch (error) { message(error.message, true); } finally { setBusy(false); }
}
async function reload() {
  const result = await request('/api/articles');
  renderArticles(result.articles);
}
async function afterWrite(text) {
  try { await reload(); message(text); }
  catch { message(`${text} The list could not refresh. Use Refresh to check the saved library.`, true); }
}
function renderArticles(articles) {
  $('#articles').replaceChildren();
  $('#count').textContent = `(${articles.length})`;
  $('#empty').hidden = articles.length !== 0;
  for (const article of articles) {
    const card = $('#article-template').content.firstElementChild.cloneNode(true);
    card.dataset.id = article.id;
    const link = $('h3 a', card);
    link.textContent = article.title; link.href = article.url;
    $('.article-url', card).textContent = article.url;
    $('.status-badge', card).textContent = statusNames[article.status];
    const form = $('.edit-form', card);
    const note = form.elements.note, status = form.elements.status;
    const draft = drafts.get(article.id) || article;
    note.value = draft.note; status.value = draft.status;
    const hint = $('.draft-hint', card);
    hint.textContent = drafts.has(article.id) ? 'Unsaved changes' : '';
    form.addEventListener('input', () => {
      if (note.value === article.note && status.value === article.status) drafts.delete(article.id);
      else drafts.set(article.id, {note: note.value, status: status.value});
      hint.textContent = drafts.has(article.id) ? 'Unsaved changes' : '';
    });
    form.addEventListener('reset', event => {
      event.preventDefault(); drafts.delete(article.id);
      note.value = article.note; status.value = article.status; hint.textContent = '';
    });
    form.addEventListener('submit', event => {
      event.preventDefault();
      action(async () => {
        const saved = await request(`/api/articles/${article.id}`, 'PATCH', {note: note.value, status: status.value});
        drafts.delete(article.id);
        // If the next read fails, the existing card still represents the confirmed save.
        Object.assign(article, saved); hint.textContent = '';
        $('.status-badge', card).textContent = statusNames[saved.status];
        await afterWrite('Reading context saved.');
      });
    });
    $('#articles').append(card);
  }
  if (busy) setBusy(true);
}
$('#capture-form').addEventListener('submit', event => {
  event.preventDefault();
  const form = event.currentTarget;
  action(async () => {
    await request('/api/articles', 'POST', {title: form.elements.title.value, url: form.elements.url.value});
    form.reset(); await afterWrite('Article saved. Existing links keep their note and progress.');
  });
});
$('#refresh').addEventListener('click', () => action(async () => { await reload(); message('Library refreshed.'); }));
window.addEventListener('beforeunload', event => { if (drafts.size) { event.preventDefault(); event.returnValue = ''; } });
action(reload);
