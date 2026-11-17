"""Serve the Reading Shelf page and JSON API with a local SQLite library."""

from pathlib import Path

from flask import Flask

from . import api, library


def create_app(instance_path: str | None = None) -> Flask:
    app = Flask(__name__, instance_path=instance_path)
    library_directory = Path(app.instance_path)
    library_directory.mkdir(parents=True, exist_ok=True)
    library_path = library_directory / "reading-shelf.sqlite3"
    # Create the schema if it is missing; an unreadable library fails during startup.
    library.initialize(library_path)
    app.config["LIBRARY_PATH"] = str(library_path)

    app.register_blueprint(api.bp)
    app.teardown_appcontext(api.close_library)

    @app.get("/")
    def index():
        return app.send_static_file("index.html")

    return app
