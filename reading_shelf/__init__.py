"""Serve the Reading Shelf starter page with a local SQLite library."""

import sqlite3
from contextlib import closing
from pathlib import Path

from flask import Flask


def create_app(instance_path: str | None = None) -> Flask:
    app = Flask(__name__, instance_path=instance_path)
    library_directory = Path(app.instance_path)
    library_directory.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(library_directory / "reading-shelf.sqlite3")) as database:
        # Read the schema so an unreadable library fails during startup.
        database.execute("PRAGMA schema_version").fetchone()

    @app.get("/")
    def index():
        return app.send_static_file("index.html")

    return app
