"""Serve the reader's library as a JSON API under ``/api``."""

from flask import Blueprint, current_app, g, jsonify, request

from . import library

bp = Blueprint("api", __name__, url_prefix="/api")


def get_library() -> library.Library:
    """Open one library connection per request and reuse it within the request."""
    if "library_connection" not in g:
        g.library_connection = library.connect(current_app.config["LIBRARY_PATH"])
    return library.Library(g.library_connection)


def close_library(_error=None) -> None:
    connection = g.pop("library_connection", None)
    if connection is not None:
        connection.close()


def json_object() -> dict:
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise library.InvalidInput("Send the request body as a JSON object.")
    return body


@bp.errorhandler(library.InvalidInput)
def invalid_input(error):
    return jsonify(error=str(error)), 400


@bp.errorhandler(library.NotFound)
def not_found(error):
    return jsonify(error=str(error)), 404


@bp.errorhandler(library.DuplicateLink)
def duplicate_link(error):
    return jsonify(error=str(error), article=error.article), 409


@bp.get("/articles")
def list_articles():
    return jsonify(articles=get_library().list_articles())


@bp.post("/articles")
def add_article():
    body = json_object()
    article = get_library().add_article(body.get("url"), body.get("title"))
    return jsonify(article), 201


@bp.get("/articles/<int:article_id>")
def get_article(article_id):
    return jsonify(get_library().get_article(article_id))


@bp.patch("/articles/<int:article_id>")
def update_article(article_id):
    return jsonify(get_library().update_article(article_id, json_object()))
