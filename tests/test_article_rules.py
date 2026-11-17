"""Check the link, title, note, status, and one-article-per-link rules at the API boundary."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from conftest import FOCACCIA_URL, save


def article_count(client):
    return len(client.get("/api/articles").get_json()["articles"])


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "ftp://example.com/article.txt",
        "en.wikipedia.org/wiki/Focaccia",
        "https://",
        "https://en.wikipedia.org/wiki/Focaccia bread",
        "",
        "   ",
        None,
        42,
    ],
)
def test_links_must_be_web_addresses(client, url):
    response = client.post("/api/articles", json={"url": url, "title": "Focaccia"})

    assert response.status_code == 400
    assert response.get_json()["error"]
    assert article_count(client) == 0


@pytest.mark.parametrize("title", ["", "   ", None, ["Focaccia"], "x" * 301])
def test_titles_must_be_present_and_reasonable(client, title):
    response = client.post("/api/articles", json={"url": FOCACCIA_URL, "title": title})

    assert response.status_code == 400
    assert article_count(client) == 0


def test_link_and_title_are_trimmed(client):
    saved = save(client, f"  {FOCACCIA_URL}  ", "  Focaccia \n bread ")

    assert saved["url"] == FOCACCIA_URL
    assert saved["title"] == "Focaccia bread"


def test_the_same_link_cannot_be_saved_twice(client):
    original = save(client)

    response = client.post("/api/articles", json={"url": f" {FOCACCIA_URL} ", "title": "Focaccia bread"})

    assert response.status_code == 409
    body = response.get_json()
    assert body["error"] == "That link is already in your library."
    assert body["article"]["id"] == original["id"]
    assert body["article"]["title"] == "Focaccia"
    assert article_count(client) == 1


def test_a_different_spelling_of_a_link_is_a_different_article(client):
    save(client)
    save(client, FOCACCIA_URL + "/", "Focaccia (slash)")

    assert article_count(client) == 2


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "done"},
        {"status": "Reading"},
        {"status": None},
        {"note": None},
        {"note": 7},
        {"note": "x" * 10_001},
        {"title": "Renamed"},
        {"url": "https://example.com"},
        {},
    ],
)
def test_edits_are_limited_to_a_valid_note_and_status(client, changes):
    article = save(client)

    response = client.patch(f"/api/articles/{article['id']}", json=changes)

    assert response.status_code == 400
    assert client.get(f"/api/articles/{article['id']}").get_json() == article


def test_a_rejected_edit_changes_nothing(client):
    article = save(client)
    url = f"/api/articles/{article['id']}"
    client.patch(url, json={"note": "Try rosemary on top.", "status": "reading"})

    response = client.patch(url, json={"note": "Overwritten?", "status": "done"})

    assert response.status_code == 400
    current = client.get(url).get_json()
    assert current["note"] == "Try rosemary on top."
    assert current["status"] == "reading"


@pytest.mark.parametrize("method", ["get", "patch"])
def test_unknown_articles_are_not_found(client, method):
    response = getattr(client, method)("/api/articles/999", json={"note": "x"})

    assert response.status_code == 404
    assert response.get_json()["error"]


@pytest.mark.parametrize("body", ["not json", "[1, 2]", "null"])
def test_requests_must_send_a_json_object(client, body):
    response = client.post("/api/articles", data=body, content_type="application/json")

    assert response.status_code == 400


def test_the_table_enforces_the_status_and_link_rules(client, instance_path):
    save(client)
    database_path = Path(instance_path) / "reading-shelf.sqlite3"

    with closing(sqlite3.connect(database_path)) as database:
        with pytest.raises(sqlite3.IntegrityError):
            database.execute(
                "INSERT INTO articles (url, title, status, saved_at) VALUES (?, ?, ?, ?)",
                ("https://example.com", "Example", "done", "2026-01-01T00:00:00Z"),
            )
        with pytest.raises(sqlite3.IntegrityError):
            database.execute(
                "INSERT INTO articles (url, title, saved_at) VALUES (?, ?, ?)",
                (FOCACCIA_URL, "Again", "2026-01-01T00:00:00Z"),
            )
