"""Serve the local Reading Shelf page and JSON API."""
import sqlite3
from pathlib import Path
from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException
from . import articles, collections, db


def create_app(instance_path: str | None = None) -> Flask:
    app = Flask(__name__, instance_path=instance_path)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    app.teardown_appcontext(db.close_db)
    with app.app_context():
        db.initialize()
    app.register_blueprint(articles.bp)
    app.register_blueprint(collections.bp)

    @app.get('/')
    def index():
        return app.send_static_file('index.html')

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.description), error.code

    @app.errorhandler(sqlite3.Error)
    def storage_error(error):
        app.logger.warning('SQLite operation failed: %s', error)
        return jsonify(error='The library could not complete this operation. Refresh to check saved data, then try again.'), 503

    return app
