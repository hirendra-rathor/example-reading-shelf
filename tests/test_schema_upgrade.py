"""Upgrade a library file written by milestone 1, and refuse one from a newer version."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from conftest import FOCACCIA_URL, collection_articles, file_under, make_collection
from reading_shelf import create_app
from reading_shelf.library import UnsupportedLibrary

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
        assert database.execute("PRAGMA user_version").fetchone()[0] == 2

    weekend = make_collection(client, "Weekend reading")
    file_under(client, weekend, focaccia)
    assert [a["note"] for a in collection_articles(client, weekend, "reading")] == ["Try rosemary on top."]


def test_a_library_from_a_newer_version_is_refused_unchanged(instance_path):
    database_path = write_library(instance_path, MILESTONE_1_SCHEMA + "PRAGMA user_version = 3;")

    with pytest.raises(UnsupportedLibrary):
        create_app(instance_path)

    with closing(sqlite3.connect(database_path)) as database:
        assert database.execute("PRAGMA user_version").fetchone()[0] == 3
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
