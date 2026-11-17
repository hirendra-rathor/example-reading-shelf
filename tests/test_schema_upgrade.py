"""Upgrade a library file written by milestone 1, and refuse one from a newer version."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from conftest import FOCACCIA_URL, collection_articles, file_under, make_collection
from reading_shelf import create_app
from reading_shelf.library import SCHEMA_VERSION, UnsupportedLibrary

# The articles table exactly as milestone 1 created it, at schema version 1.
MILESTONE_1_SCHEMA = """
CREATE TABLE articles (
    id INTEGER PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'to_read'
        CHECK (status IN ('to_read', 'reading', 'read')),
    saved_at TEXT NOT NULL
);
PRAGMA user_version = 1;
"""


def write_library(instance_path, script):
    database_path = Path(instance_path) / "reading-shelf.sqlite3"
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database_path)) as database:
        database.executescript(script)
        database.commit()
    return database_path


def test_a_milestone_1_library_is_upgraded_and_keeps_its_articles(instance_path):
    database_path = write_library(
        instance_path,
        MILESTONE_1_SCHEMA
        + f"""
        INSERT INTO articles (url, title, note, status, saved_at)
        VALUES ('{FOCACCIA_URL}', 'Focaccia', 'Try rosemary on top.', 'reading', '2026-11-17T19:15:19Z');
        """,
    )

    client = create_app(instance_path).test_client()

    [focaccia] = client.get("/api/articles").get_json()["articles"]
    assert (focaccia["title"], focaccia["note"], focaccia["status"]) == ("Focaccia", "Try rosemary on top.", "reading")
    assert focaccia["collection_ids"] == []
    with closing(sqlite3.connect(database_path)) as database:
        assert database.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION

    weekend = make_collection(client, "Weekend reading")
    file_under(client, weekend, focaccia)
    assert [a["note"] for a in collection_articles(client, weekend, "reading")] == ["Try rosemary on top."]


def test_a_library_from_a_newer_version_is_refused_unchanged(instance_path):
    newer = SCHEMA_VERSION + 1
    database_path = write_library(instance_path, MILESTONE_1_SCHEMA + f"PRAGMA user_version = {newer};")

    with pytest.raises(UnsupportedLibrary):
        create_app(instance_path)

    with closing(sqlite3.connect(database_path)) as database:
        assert database.execute("PRAGMA user_version").fetchone()[0] == newer
        tables = {row[0] for row in database.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert tables == {"articles"}


def test_memberships_follow_their_article_and_collection(client, instance_path):
    """Foreign keys are enforced, so a membership can't point at a missing article."""
    database_path = Path(instance_path) / "reading-shelf.sqlite3"
    with closing(sqlite3.connect(database_path)) as database:
        database.execute("PRAGMA foreign_keys = ON")
        with pytest.raises(sqlite3.IntegrityError):
            database.execute(
                "INSERT INTO collection_articles (collection_id, article_id, added_at) VALUES (1, 1, 'now')"
            )


# The tables exactly as milestone 2 created them, at schema version 2.
MILESTONE_2_SCHEMA = MILESTONE_1_SCHEMA.replace("PRAGMA user_version = 1;", "") + """
CREATE TABLE collections (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    name_key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);
CREATE TABLE collection_articles (
    collection_id INTEGER NOT NULL REFERENCES collections (id) ON DELETE CASCADE,
    article_id INTEGER NOT NULL REFERENCES articles (id) ON DELETE CASCADE,
    added_at TEXT NOT NULL,
    PRIMARY KEY (collection_id, article_id)
);
PRAGMA user_version = 2;
"""


def test_a_milestone_2_library_is_upgraded_with_its_collections(instance_path):
    database_path = write_library(
        instance_path,
        MILESTONE_2_SCHEMA
        + f"""
        INSERT INTO articles (url, title, note, status, saved_at)
        VALUES ('{FOCACCIA_URL}', 'Focaccia', 'Stopped at the shaping step.', 'reading', '2026-11-17T19:15:19Z');
        INSERT INTO collections (name, name_key, created_at) VALUES
            ('Food and cooking', 'food and cooking', '2026-11-17T19:30:06Z'),
            ('Weekend reading', 'weekend reading', '2026-11-17T19:30:07Z');
        INSERT INTO collection_articles (collection_id, article_id, added_at) VALUES
            (1, 1, '2026-11-17T19:30:20Z'), (2, 1, '2026-11-17T19:30:21Z');
        """,
    )

    client = create_app(instance_path).test_client()

    [focaccia] = client.get("/api/articles").get_json()["articles"]
    assert focaccia["archived_at"] is None
    assert focaccia["collection_ids"] == [1, 2]
    assert (focaccia["note"], focaccia["status"]) == ("Stopped at the shaping step.", "reading")
    with closing(sqlite3.connect(database_path)) as database:
        assert database.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION == 3
        columns = [row[1] for row in database.execute("PRAGMA table_info(articles)")]
    assert "archived_at" in columns

    create_app(instance_path)  # A second start must not try to add the column again.
    assert client.post("/api/articles/1/archive").get_json()["collection_ids"] == [1, 2]
