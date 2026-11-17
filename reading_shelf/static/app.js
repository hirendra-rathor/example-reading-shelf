"use strict";

// Reading Shelf page script: renders the library and sends saves and edits to the JSON API.
// Reader-supplied text is always assigned with textContent or value, never parsed as HTML.

const STATUS_LABELS = { to_read: "To read", reading: "Reading", read: "Read" };

const state = { articles: [] };

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

function renderArticle(article) {
  const item = elements.template.content.firstElementChild.cloneNode(true);
  item.dataset.id = String(article.id);

  const link = item.querySelector(".article-title");
  link.href = article.url;
  link.querySelector(".title-text").textContent = article.title;
  item.querySelector(".article-host").textContent = hostOf(article.url);

  const picker = item.querySelector(".status-picker");
  for (const button of picker.querySelectorAll("button")) {
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
  return item;
}

function render() {
  const items = state.articles.map(renderArticle);
  elements.list.replaceChildren(...items);
  elements.empty.hidden = state.articles.length > 0;
  const count = state.articles.length;
  elements.count.textContent = count === 1 ? "1 article" : `${count} articles`;
}

function replaceArticle(updated) {
  state.articles = state.articles.map((article) => (article.id === updated.id ? updated : article));
}

function highlight(articleId) {
  const item = elements.list.querySelector(`[data-id="${articleId}"]`);
  if (!item) return;
  item.classList.add("highlight");
  item.scrollIntoView({ behavior: "smooth", block: "nearest" });
  setTimeout(() => item.classList.remove("highlight"), 2500);
}

async function loadLibrary() {
  try {
    const data = await api("/api/articles");
    state.articles = data.articles;
    render();
    showMessage(elements.libraryMessage, "");
  } catch (error) {
    showMessage(elements.libraryMessage, error.message, "error");
  }
}

async function addArticle(event) {
  event.preventDefault();
  const button = elements.form.querySelector("button[type=submit]");
  button.disabled = true;
  try {
    const article = await api("/api/articles", {
      method: "POST",
      body: { title: elements.title.value, url: elements.url.value },
    });
    state.articles = [article, ...state.articles];
    render();
    elements.form.reset();
    showMessage(elements.addMessage, `Saved “${article.title}”.`, "ok");
    highlight(article.id);
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

async function changeStatus(articleId, status, item) {
  const message = item.querySelector(".note-message");
  try {
    const updated = await api(`/api/articles/${articleId}`, { method: "PATCH", body: { status } });
    replaceArticle(updated);
    for (const button of item.querySelectorAll(".status-picker button")) {
      button.setAttribute("aria-pressed", String(button.dataset.status === updated.status));
    }
    showMessage(message, `Marked “${STATUS_LABELS[updated.status]}”.`, "ok");
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
    replaceArticle(updated);
    showMessage(message, "Note saved.", "ok");
  } catch (error) {
    // Keep the reader's text in the box so nothing they typed is lost.
    showMessage(message, error.message, "error");
  } finally {
    button.disabled = false;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  elements.form = document.getElementById("add-form");
  elements.title = document.getElementById("add-title");
  elements.url = document.getElementById("add-url");
  elements.addMessage = document.getElementById("add-message");
  elements.list = document.getElementById("article-list");
  elements.empty = document.getElementById("empty-library");
  elements.count = document.getElementById("library-count");
  elements.libraryMessage = document.getElementById("library-message");
  elements.template = document.getElementById("article-template");
  elements.form.addEventListener("submit", addArticle);
  loadLibrary();
});
