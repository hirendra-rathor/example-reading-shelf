"""Exercise the starter page and local database through the Flask application factory."""

import sqlite3
from contextlib import closing

from reading_shelf import create_app


def test_starter_serves_page_and_preserves_the_local_database(tmp_path):
    instance_path = tmp_path / "instance"
    database_path = instance_path / "reading-shelf.sqlite3"

    app = create_app(str(instance_path))
    response = app.test_client().get("/")
    assert response.status_code == 200
    assert "<h1>Reading Shelf</h1>" in response.get_data(as_text=True)
    assert database_path.is_file()

    with closing(sqlite3.connect(database_path)) as database:
        database.execute("CREATE TABLE restart_probe (value TEXT)")
        database.execute("INSERT INTO restart_probe VALUES (?)", ("before restart",))
        database.commit()

    create_app(str(instance_path))
    with closing(sqlite3.connect(database_path)) as database:
        assert database.execute("SELECT value FROM restart_probe").fetchall() == [("before restart",)]
