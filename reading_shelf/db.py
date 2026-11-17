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
        connection.execute('''CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            note TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'to_read'
                CHECK (status IN ('to_read', 'reading', 'read'))
        )''')
