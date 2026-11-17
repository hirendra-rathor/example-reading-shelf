"""Save, list, and annotate articles through the JSON API, including across a restart."""

import sqlite3
from contextlib import closing
from pathlib import Path

from conftest import FOCACCIA_URL, save


def test_saved_article_is_listed_as_to_read_with_an_empty_note(client):
    saved = save(client)

    assert saved["url"] == FOCACCIA_URL
    assert saved["title"] == "Focaccia"
    assert saved["status"] == "to_read"
    assert saved["note"] == ""
    assert saved["saved_at"].endswith("Z")

    listed = client.get("/api/articles").get_json()["articles"]
    assert listed == [saved]


def test_note_and_reading_status_survive_a_restart(client, restart):
    article = save(client)
    response = client.patch(
        f"/api/articles/{article['id']}",
        json={"note": "Try rosemary on top.", "status": "reading"},
    )
    assert response.status_code == 200

    after_restart = restart().get("/api/articles").get_json()["articles"]

    assert len(after_restart) == 1
    assert after_restart[0]["id"] == article["id"]
    assert after_restart[0]["url"] == FOCACCIA_URL
    assert after_restart[0]["note"] == "Try rosemary on top."
    assert after_restart[0]["status"] == "reading"


def test_editing_the_note_replaces_it_and_an_empty_note_clears_it(client):
    article = save(client)
    url = f"/api/articles/{article['id']}"

    client.patch(url, json={"note": "Try rosemary on top."})
    assert client.patch(url, json={"note": "Use flaky salt."}).get_json()["note"] == "Use flaky salt."
    assert client.get(url).get_json()["note"] == "Use flaky salt."

    assert client.patch(url, json={"note": ""}).get_json()["note"] == ""


def test_changing_status_keeps_the_note(client):
    article = save(client)
    url = f"/api/articles/{article['id']}"
    client.patch(url, json={"note": "Try rosemary on top."})

    for status in ("reading", "read", "to_read"):
        updated = client.patch(url, json={"status": status}).get_json()
        assert updated["status"] == status
        assert updated["note"] == "Try rosemary on top."


def test_library_lists_newest_first(client):
    first = save(client, "https://example.com/first", "First")
    second = save(client, "https://example.com/second", "Second")

    listed = client.get("/api/articles").get_json()["articles"]

    assert [article["id"] for article in listed] == [second["id"], first["id"]]


def test_page_serves_the_library_interface(client):
    page = client.get("/").get_data(as_text=True)
    assert '<form id="add-form"' in page
    assert 'id="article-list"' in page
    assert 'rel="noopener noreferrer"' in page
    for status in ("to_read", "reading", "read"):
        assert f'data-status="{status}"' in page

    script = client.get("/static/app.js")
    assert script.status_code == 200
    assert "textContent" in script.get_data(as_text=True)


def test_schema_is_versioned_and_created_only_once(client, restart, instance_path):
    save(client)
    restart()
    restart()

    database_path = Path(instance_path) / "reading-shelf.sqlite3"
    with closing(sqlite3.connect(database_path)) as database:
        assert database.execute("PRAGMA user_version").fetchone()[0] == 2
        assert database.execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 1
