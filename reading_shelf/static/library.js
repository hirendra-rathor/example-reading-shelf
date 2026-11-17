'use strict';
const $ = (selector, root = document) => root.querySelector(selector);
const statusNames = {to_read: 'To read', reading: 'Reading', read: 'Read'};
const drafts = new Map();
let busy = false;
let collections = [];
let filters = {collection_id: '', status: '', view: 'active'};

function message(text, error = false) {
  $('#message').textContent = text;
  $('#message').classList.toggle('error', error);
}
function setBusy(value) {
  busy = value;
  document.querySelectorAll('button, input, textarea, select').forEach(control => { control.disabled = value || control.dataset.unavailable === 'true'; });
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
function showFilters() {
  $('#view-filter').value = filters.view;
  $('#collection-filter').value = filters.collection_id;
  $('#status-filter').value = filters.status;
}
function requireSavedDrafts() {
  if (drafts.size) throw new Error('Save or revert your article edits before changing the view or memberships.');
}
async function reload(nextFilters = filters) {
  const query = new URLSearchParams(Object.entries(nextFilters).filter(([,value]) => value !== ''));
  const [catalog, result] = await Promise.all([request('/api/collections'), request(`/api/articles?${query}`)]);
  collections = catalog.collections; filters = {...nextFilters};
  $('#collection-filter').replaceChildren(new Option('Whole library', ''), ...collections.map(c => new Option(c.name, c.id)));
  showFilters(); renderArticles(result.articles);
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
    $('.status-badge', card).textContent = statusNames[article.status] + (article.archived ? ' · Archived' : '');
    card.classList.toggle('archived', article.archived);
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
    const memberships = $('.memberships', card);
    for (const collection of collections.filter(c => article.collection_ids.includes(c.id))) {
      const remove = document.createElement('button');
      remove.type = 'button'; remove.className = 'secondary';
      remove.textContent = `${collection.name} ×`;
      remove.setAttribute('aria-label', `Remove from ${collection.name}`);
      remove.addEventListener('click', () => action(async () => {
        requireSavedDrafts();
        await request(`/api/collections/${collection.id}/articles/${article.id}`, 'DELETE');
        await afterWrite(`Removed from ${collection.name}. The article remains in your library.`);
      }));
      memberships.append(remove);
    }
    const memberForm = $('.membership-form', card);
    const available = collections.filter(c => !article.collection_ids.includes(c.id));
    memberForm.elements.collection.replaceChildren(new Option('Choose a collection', ''), ...available.map(c => new Option(c.name, c.id)));
    memberForm.querySelectorAll('select,button').forEach(e => { e.dataset.unavailable = String(available.length === 0); });
    memberForm.addEventListener('submit', event => {
      event.preventDefault(); action(async () => {
        requireSavedDrafts();
        const id = memberForm.elements.collection.value;
        if (!id) throw new Error('Choose a collection first.');
        await request(`/api/collections/${id}/articles/${article.id}`, 'PUT');
        await afterWrite('Article added to the collection.');
      });
    });
    if (article.archived) {
      card.querySelectorAll('.edit-form input,.edit-form textarea,.edit-form select,.edit-form button,.memberships button').forEach(e => { e.dataset.unavailable = 'true'; });
      memberForm.hidden = true;
      hint.textContent = 'Restore this article to edit its note, status, or collections.';
    }
    const archiveButton = $('.archive-action', card);
    archiveButton.textContent = article.archived ? 'Restore article' : 'Archive article';
    archiveButton.addEventListener('click', () => action(async () => {
      requireSavedDrafts();
      await request(`/api/articles/${article.id}/archive`, article.archived ? 'DELETE' : 'PUT');
      card.remove();
      const remaining = document.querySelectorAll('#articles > .article').length;
      $('#count').textContent = `(${remaining})`; $('#empty').hidden = remaining !== 0;
      await afterWrite(article.archived ? 'Article restored with its reading context and collections.' : 'Article archived. Find it in the Archive view.');
    }));
    $('#articles').append(card);
  }
  if (busy) setBusy(true);
}
$('#capture-form').addEventListener('submit', event => {
  event.preventDefault();
  const form = event.currentTarget;
  action(async () => {
    const saved = await request('/api/articles', 'POST', {title: form.elements.title.value, url: form.elements.url.value});
    form.reset(); await afterWrite(saved.archived ? 'This article is archived. Open Archive to restore it.' : 'Article saved. Existing links keep their note and progress.');
  });
});
$('#collection-form').addEventListener('submit', event => {
  event.preventDefault(); const form = event.currentTarget;
  action(async () => { await request('/api/collections', 'POST', {name:form.elements.name.value}); form.reset(); await afterWrite('Collection ready. Add articles using their collection controls.'); });
});
for (const selector of ['#collection-filter', '#status-filter']) {
  $(selector).addEventListener('change', () => action(async () => {
    try {
      requireSavedDrafts();
      await reload({collection_id:$('#collection-filter').value, status:$('#status-filter').value, view:filters.view});
      message('Library view updated.');
    } finally { showFilters(); }
  }));
}
$('#view-filter').addEventListener('change', () => action(async () => {
  try { requireSavedDrafts(); await reload({collection_id:'', status:'', view:$('#view-filter').value}); message(filters.view === 'archive' ? 'Your archived articles.' : 'Your active library.'); } finally { showFilters(); }
}));
$('#refresh').addEventListener('click', () => action(async () => { await reload(); message('Library refreshed.'); }));
window.addEventListener('beforeunload', event => { if (drafts.size) { event.preventDefault(); event.returnValue = ''; } });
action(reload);
