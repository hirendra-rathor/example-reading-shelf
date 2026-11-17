"""Request-scoped SQLite access and additive schema initialization."""
import sqlite3
from pathlib import Path
from flask import current_app, g


def get_db():
    if 'database' not in g:
        connection = sqlite3.connect(Path(current_app.instance_path) / 'reading-shelf.sqlite3')
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys = ON')
        g.database = connection
    return g.database


def close_db(error=None):
    connection = g.pop('database', None)
    if connection is not None:
        connection.close()


def initialize():
    connection = get_db()
    with connection:
        connection.execute('BEGIN IMMEDIATE')
        connection.execute('''CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            note TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'to_read'
                CHECK (status IN ('to_read', 'reading', 'read'))
        )''')
        connection.execute('''CREATE TABLE IF NOT EXISTS collections (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, name_key TEXT NOT NULL UNIQUE
        )''')
        connection.execute('''CREATE TABLE IF NOT EXISTS collection_articles (
            collection_id INTEGER NOT NULL REFERENCES collections(id),
            article_id INTEGER NOT NULL REFERENCES articles(id),
            PRIMARY KEY (collection_id, article_id)
        )''')
        connection.execute('CREATE INDEX IF NOT EXISTS memberships_by_article ON collection_articles(article_id)')
        columns = {row['name'] for row in connection.execute('PRAGMA table_info(articles)')}
        if 'archived' not in columns:
            connection.execute('ALTER TABLE articles ADD COLUMN archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0, 1))')
