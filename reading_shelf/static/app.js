"use strict";

// Reading Shelf page script: renders the library or one collection, optionally narrowed to
// one reading status, and sends saves and edits to the JSON API. Collections reference the
// same article, so every view reads note and status from the API rather than keeping copies.
// Reader-supplied text is always assigned with textContent or value, never parsed as HTML.

const STATUS_LABELS = { to_read: "To read", reading: "Reading", read: "Read" };

const state = {
  view: { collectionId: null, status: null },
  collection: null,
  collections: [],
  articles: [],
};

const elements = {};

class ApiError extends Error {
  constructor(message, status, body) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

async function api(path, { method = "GET", body } = {}) {
  const options = { method, headers: { Accept: "application/json" } };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(path, options);
  } catch {
    throw new ApiError("Couldn’t reach Reading Shelf. Is the app running?", 0, null);
  }
  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }
  if (!response.ok) {
    throw new ApiError((data && data.error) || `Request failed (${response.status}).`, response.status, data);
  }
  return data;
}

function showMessage(element, text, tone = "") {
  element.textContent = text;
  element.classList.toggle("error", tone === "error");
  element.classList.toggle("ok", tone === "ok");
}

function hostOf(url) {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

// ------------------------------------------------------------------ views

function readViewFromLocation() {
  const params = new URLSearchParams(window.location.hash.slice(1));
  const collectionId = Number.parseInt(params.get("collection") || "", 10);
  const status = params.get("status");
  return {
    collectionId: Number.isInteger(collectionId) && collectionId > 0 ? collectionId : null,
    status: status in STATUS_LABELS ? status : null,
  };
}

function viewHash({ collectionId, status }) {
  const params = new URLSearchParams();
  if (collectionId) params.set("collection", String(collectionId));
  if (status) params.set("status", status);
  const text = params.toString();
  return text ? `#${text}` : "#";
}

function goTo(view) {
  const hash = viewHash(view);
  if (hash === (window.location.hash || "#")) {
    loadView();
  } else {
    window.location.hash = hash;
  }
}

function collectionName(collectionId) {
  const found = state.collections.find((collection) => collection.id === collectionId);
  return found ? found.name : "a collection";
}

function inView(article) {
  const { collectionId, status } = state.view;
  if (status && article.status !== status) return false;
  if (collectionId && !article.collection_ids.includes(collectionId)) return false;
  return true;
}

async function loadCollections() {
  const data = await api("/api/collections");
  state.collections = data.collections;
  renderViewList();
}

async function loadView() {
  state.view = readViewFromLocation();
  const { collectionId, status } = state.view;
  const query = status ? `?status=${status}` : "";
  try {
    const [collections, listing] = await Promise.all([
      api("/api/collections"),
      collectionId ? api(`/api/collections/${collectionId}/articles${query}`) : api(`/api/articles${query}`),
    ]);
    state.collections = collections.collections;
    state.collection = collectionId ? listing.collection : null;
    state.articles = listing.articles;
    showMessage(elements.libraryMessage, "");
  } catch (error) {
    if (error.status === 404 && collectionId) {
      showMessage(elements.libraryMessage, "That collection doesn’t exist. Showing all articles.", "error");
      goTo({ collectionId: null, status });
      return;
    }
    showMessage(elements.libraryMessage, error.message, "error");
    return;
  }
  render();
}

// --------------------------------------------------------------- rendering

function renderViewList() {
  const { collectionId, status } = state.view;
  const entries = [{ id: null, name: "All articles", count: null }].concat(
    state.collections.map((collection) => ({ id: collection.id, name: collection.name, count: collection.article_count })),
  );
  const items = entries.map((entry) => {
    const item = document.createElement("li");
    const link = document.createElement("a");
    link.href = viewHash({ collectionId: entry.id, status });
    link.className = "view-link";
    if (entry.id === collectionId) link.setAttribute("aria-current", "page");
    const name = document.createElement("span");
    name.textContent = entry.name;
    link.append(name);
    if (entry.count !== null) {
      const count = document.createElement("span");
      count.className = "view-count";
      count.textContent = String(entry.count);
      count.setAttribute("aria-label", entry.count === 1 ? "1 article" : `${entry.count} articles`);
      link.append(count);
    }
    item.append(link);
    return item;
  });
  elements.viewList.replaceChildren(...items);
}

function renderMemberships(item, article) {
  const chips = item.querySelector(".chips");
  const chipItems = article.collection_ids.map((collectionId) => {
    const chip = document.createElement("li");
    chip.className = "chip";
    const link = document.createElement("a");
    link.href = viewHash({ collectionId, status: state.view.status });
    link.textContent = collectionName(collectionId);
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "chip-remove";
    remove.textContent = "×";
    remove.setAttribute("aria-label", `Remove from ${collectionName(collectionId)}`);
    remove.title = `Remove from ${collectionName(collectionId)}`;
    remove.addEventListener("click", () => removeFromCollection(article.id, collectionId, item));
    chip.append(link, remove);
    return chip;
  });
  chips.replaceChildren(...chipItems);

  const select = item.querySelector(".add-to-collection");
  const placeholder = new Option(state.collections.length ? "Add to collection…" : "No collections yet", "");
  const options = state.collections
    .filter((collection) => !article.collection_ids.includes(collection.id))
    .map((collection) => new Option(collection.name, String(collection.id)));
  select.replaceChildren(placeholder, ...options);
  select.disabled = options.length === 0;
}

function renderArticle(article) {
  const item = elements.template.content.firstElementChild.cloneNode(true);
  item.dataset.id = String(article.id);

  const link = item.querySelector(".article-title");
  link.href = article.url;
  link.querySelector(".title-text").textContent = article.title;
  item.querySelector(".article-host").textContent = hostOf(article.url);

  for (const button of item.querySelectorAll(".status-picker button")) {
    button.setAttribute("aria-pressed", String(button.dataset.status === article.status));
    button.addEventListener("click", () => changeStatus(article.id, button.dataset.status, item));
  }

  const noteId = `note-${article.id}`;
  const textarea = item.querySelector(".note");
  textarea.id = noteId;
  textarea.value = article.note;
  item.querySelector(".note-label").htmlFor = noteId;
  item.querySelector(".save-note").addEventListener("click", () => saveNote(article.id, item));
  textarea.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      saveNote(article.id, item);
    }
  });
  textarea.addEventListener("input", () => showMessage(item.querySelector(".note-message"), "Unsaved changes"));

  renderMemberships(item, article);
  item.querySelector(".add-to-collection").addEventListener("change", (event) => {
    const collectionId = Number.parseInt(event.target.value, 10);
    if (collectionId) addToCollection(article.id, collectionId, item);
  });
  return item;
}

function emptyMessage() {
  const { collectionId, status } = state.view;
  const where = collectionId ? `in ${collectionName(collectionId)}` : "in your library";
  if (status) return `No articles marked ${STATUS_LABELS[status]} ${where}.`;
  if (collectionId) return `Nothing in ${collectionName(collectionId)} yet. Use “Add to collection…” on any article.`;
  return "Nothing saved yet. Add an article to start your library.";
}

function renderSummary() {
  const count = state.articles.length;
  const statusText = state.view.status ? ` · ${STATUS_LABELS[state.view.status]}` : "";
  elements.count.textContent = `${count === 1 ? "1 article" : `${count} articles`}${statusText}`;
  elements.empty.hidden = count > 0;
  elements.empty.textContent = emptyMessage();
}

function render() {
  const { collectionId, status } = state.view;
  elements.viewKind.textContent = collectionId ? "Collection" : "Library";
  elements.viewHeading.textContent = collectionId ? state.collection.name : "All articles";
  for (const button of elements.filterButtons) {
    button.setAttribute("aria-pressed", String((button.dataset.filter || null) === status));
  }
  renderViewList();
  elements.list.replaceChildren(...state.articles.map(renderArticle));
  renderSummary();
}

// Apply an updated article to the current view without disturbing other cards,
// so unsaved notes elsewhere on the page are kept.
function applyUpdate(updated, item, departureMessage) {
  if (!inView(updated)) {
    state.articles = state.articles.filter((article) => article.id !== updated.id);
    item.remove();
    renderSummary();
    showMessage(elements.libraryMessage, departureMessage, "ok");
    return false;
  }
  state.articles = state.articles.map((article) => (article.id === updated.id ? updated : article));
  return true;
}

function highlight(articleId) {
  const item = elements.list.querySelector(`[data-id="${articleId}"]`);
  if (!item) return;
  item.classList.add("highlight");
  item.scrollIntoView({ behavior: "smooth", block: "nearest" });
  setTimeout(() => item.classList.remove("highlight"), 2500);
}

// ----------------------------------------------------------------- actions

async function addArticle(event) {
  event.preventDefault();
  const button = elements.form.querySelector("button[type=submit]");
  button.disabled = true;
  try {
    const article = await api("/api/articles", {
      method: "POST",
      body: { title: elements.title.value, url: elements.url.value },
    });
    elements.form.reset();
    if (inView(article)) {
      state.articles = [article, ...state.articles];
      elements.list.prepend(renderArticle(article));
      renderSummary();
      highlight(article.id);
      showMessage(elements.addMessage, `Saved “${article.title}”.`, "ok");
    } else {
      showMessage(elements.addMessage, `Saved “${article.title}” to your library.`, "ok");
    }
    elements.title.focus();
  } catch (error) {
    if (error.status === 409 && error.body && error.body.article) {
      showMessage(elements.addMessage, `Already in your library as “${error.body.article.title}”.`, "error");
      highlight(error.body.article.id);
    } else {
      showMessage(elements.addMessage, error.message, "error");
    }
  } finally {
    button.disabled = false;
  }
}

async function createCollection(event) {
  event.preventDefault();
  const button = elements.collectionForm.querySelector("button[type=submit]");
  button.disabled = true;
  try {
    const collection = await api("/api/collections", { method: "POST", body: { name: elements.collectionName.value } });
    elements.collectionForm.reset();
    showMessage(elements.collectionMessage, `Created “${collection.name}”.`, "ok");
    await loadCollections();
    for (const item of elements.list.querySelectorAll(".article")) {
      const article = state.articles.find((entry) => String(entry.id) === item.dataset.id);
      if (article) renderMemberships(item, article);
    }
  } catch (error) {
    showMessage(elements.collectionMessage, error.message, "error");
  } finally {
    button.disabled = false;
  }
}

async function changeStatus(articleId, status, item) {
  const message = item.querySelector(".note-message");
  try {
    const updated = await api(`/api/articles/${articleId}`, { method: "PATCH", body: { status } });
    const label = STATUS_LABELS[updated.status];
    if (!applyUpdate(updated, item, `Marked “${updated.title}” ${label}; it no longer matches this view.`)) return;
    for (const button of item.querySelectorAll(".status-picker button")) {
      button.setAttribute("aria-pressed", String(button.dataset.status === updated.status));
    }
    showMessage(message, `Marked “${label}”.`, "ok");
  } catch (error) {
    showMessage(message, error.message, "error");
  }
}

async function saveNote(articleId, item) {
  const textarea = item.querySelector(".note");
  const message = item.querySelector(".note-message");
  const button = item.querySelector(".save-note");
  button.disabled = true;
  try {
    const updated = await api(`/api/articles/${articleId}`, { method: "PATCH", body: { note: textarea.value } });
    applyUpdate(updated, item, "");
    showMessage(message, "Note saved.", "ok");
  } catch (error) {
    // Keep the reader's text in the box so nothing they typed is lost.
    showMessage(message, error.message, "error");
  } finally {
    button.disabled = false;
  }
}

async function addToCollection(articleId, collectionId, item) {
  const message = item.querySelector(".note-message");
  try {
    const updated = await api(`/api/collections/${collectionId}/articles/${articleId}`, { method: "PUT" });
    await loadCollections();
    if (applyUpdate(updated, item, "")) renderMemberships(item, updated);
    showMessage(message, `Added to ${collectionName(collectionId)}.`, "ok");
  } catch (error) {
    showMessage(message, error.message, "error");
    await loadCollections();
  }
}

async function removeFromCollection(articleId, collectionId, item) {
  const message = item.querySelector(".note-message");
  const name = collectionName(collectionId);
  try {
    const updated = await api(`/api/collections/${collectionId}/articles/${articleId}`, { method: "DELETE" });
    await loadCollections();
    if (applyUpdate(updated, item, `Removed “${updated.title}” from ${name}. It’s still in your library.`)) {
      renderMemberships(item, updated);
      showMessage(message, `Removed from ${name}.`, "ok");
    }
  } catch (error) {
    showMessage(message, error.message, "error");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  elements.form = document.getElementById("add-form");
  elements.title = document.getElementById("add-title");
  elements.url = document.getElementById("add-url");
  elements.addMessage = document.getElementById("add-message");
  elements.collectionForm = document.getElementById("collection-form");
  elements.collectionName = document.getElementById("collection-name");
  elements.collectionMessage = document.getElementById("collection-message");
  elements.viewList = document.getElementById("view-list");
  elements.viewKind = document.getElementById("view-kind");
  elements.viewHeading = document.getElementById("view-heading");
  elements.filterButtons = document.querySelectorAll(".status-filter button");
  elements.list = document.getElementById("article-list");
  elements.empty = document.getElementById("empty-library");
  elements.count = document.getElementById("library-count");
  elements.libraryMessage = document.getElementById("library-message");
  elements.template = document.getElementById("article-template");

  elements.form.addEventListener("submit", addArticle);
  elements.collectionForm.addEventListener("submit", createCollection);
  for (const button of elements.filterButtons) {
    button.addEventListener("click", () => goTo({ collectionId: state.view.collectionId, status: button.dataset.filter || null }));
  }
  window.addEventListener("hashchange", loadView);
  loadView();
});
