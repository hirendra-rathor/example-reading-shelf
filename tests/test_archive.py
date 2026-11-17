"""Archive an article in two collections, restart, restore, and check that everything comes back."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from conftest import (
    FOCACCIA_URL,
    collection_articles,
    file_under,
    library_articles,
    make_collection,
    save,
)

# The fields that make up "everything" a reader expects back after a restore.
RESTORED_FIELDS = ("id", "url", "title", "note", "status", "saved_at", "collection_ids")


@pytest.fixture
def shelf(client):
    """Focaccia, halfway through: Reading, with a note, in both collections."""
    focaccia = save(client)
    client.patch(
        f"/api/articles/{focaccia['id']}",
        json={"note": "Stopped at the shaping step.", "status": "reading"},
    )
    food = make_collection(client, "Food and cooking")
    weekend = make_collection(client, "Weekend reading")
    file_under(client, food, focaccia)
    file_under(client, weekend, focaccia)
    return client, client.get(f"/api/articles/{focaccia['id']}").get_json(), food, weekend


def snapshot(article):
    return {field: article[field] for field in RESTORED_FIELDS}


def counts(client):
    return {c["name"]: c["article_count"] for c in client.get("/api/collections").get_json()["collections"]}


def archive_ids(client):
    return [a["id"] for a in client.get("/api/archive").get_json()["articles"]]


def test_a_restored_article_comes_back_exactly_after_a_restart(shelf, restart):
    client, focaccia, food, weekend = shelf
    before = snapshot(focaccia)

    archived = client.post(f"/api/articles/{focaccia['id']}/archive")
    assert archived.status_code == 200
    assert archived.get_json()["archived_at"]

    client = restart()
    assert archive_ids(client) == [focaccia["id"]]

    restored = client.post(f"/api/articles/{focaccia['id']}/restore")
    assert restored.status_code == 200
    assert restored.get_json()["archived_at"] is None
    assert snapshot(restored.get_json()) == before

    client = restart()
    assert [snapshot(a) for a in library_articles(client)] == [before]
    for collection in (food, weekend):
        [back] = collection_articles(client, collection, "reading")
        assert snapshot(back) == before
        assert back["url"] == FOCACCIA_URL
    assert archive_ids(client) == []
    assert counts(client) == {"Food and cooking": 1, "Weekend reading": 1}


def test_an_archived_article_is_hidden_from_every_view(shelf, restart):
    client, focaccia, food, weekend = shelf

    client.post(f"/api/articles/{focaccia['id']}/archive")

    for current in (client, restart()):
        assert library_articles(current) == []
        assert library_articles(current, "reading") == []
        for collection in (food, weekend):
            assert collection_articles(current, collection) == []
            assert collection_articles(current, collection, "reading") == []
        assert counts(current) == {"Food and cooking": 0, "Weekend reading": 0}
        [in_archive] = current.get("/api/archive").get_json()["articles"]
        assert in_archive["collection_ids"] == sorted([food["id"], weekend["id"]])
        assert in_archive["note"] == "Stopped at the shaping step."
        assert in_archive["status"] == "reading"


def test_archiving_keeps_the_memberships_in_the_file(shelf, instance_path):
    client, focaccia, food, weekend = shelf
    database_path = Path(instance_path) / "reading-shelf.sqlite3"

    def stored_rows():
        with closing(sqlite3.connect(database_path)) as database:
            article = database.execute(
                "SELECT url, title, note, status FROM articles WHERE id = ?", (focaccia["id"],)
            ).fetchone()
            members = database.execute(
                "SELECT collection_id FROM collection_articles WHERE article_id = ? ORDER BY collection_id",
                (focaccia["id"],),
            ).fetchall()
        return article, members

    before = stored_rows()
    client.post(f"/api/articles/{focaccia['id']}/archive")

    assert stored_rows() == before
    assert before[1] == [(food["id"],), (weekend["id"],)]


def test_the_archive_lists_most_recently_archived_first_and_filters_by_status(shelf):
    client, focaccia, food, weekend = shelf
    sourdough = save(client, "https://en.wikipedia.org/wiki/Sourdough", "Sourdough")

    client.post(f"/api/articles/{focaccia['id']}/archive")
    client.post(f"/api/articles/{sourdough['id']}/archive")

    assert archive_ids(client) in ([sourdough["id"], focaccia["id"]], [focaccia["id"], sourdough["id"]])
    assert [a["id"] for a in client.get("/api/archive?status=reading").get_json()["articles"]] == [focaccia["id"]]
    assert [a["id"] for a in client.get("/api/archive?status=to_read").get_json()["articles"]] == [sourdough["id"]]


def test_other_articles_stay_in_view_while_one_is_archived(shelf):
    client, focaccia, food, weekend = shelf
    sourdough = save(client, "https://en.wikipedia.org/wiki/Sourdough", "Sourdough")
    file_under(client, weekend, sourdough)

    client.post(f"/api/articles/{focaccia['id']}/archive")

    assert [a["title"] for a in library_articles(client)] == ["Sourdough"]
    assert [a["title"] for a in collection_articles(client, weekend)] == ["Sourdough"]
    assert counts(client) == {"Food and cooking": 0, "Weekend reading": 1}


def test_page_offers_archive_and_restore(client):
    page = client.get("/").get_data(as_text=True)

    assert 'class="archive-button"' in page
    assert '<template id="archived-template">' in page
    assert 'class="restore-button' in page
    assert "/api/archive" in client.get("/static/app.js").get_data(as_text=True)
