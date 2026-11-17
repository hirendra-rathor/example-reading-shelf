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


def status_filter() -> str | None:
    return library.clean_status_filter(request.args.get("status"))


@bp.errorhandler(library.InvalidInput)
def invalid_input(error):
    return jsonify(error=str(error)), 400


@bp.errorhandler(library.NotFound)
def not_found(error):
    return jsonify(error=str(error)), 404


@bp.errorhandler(library.DuplicateLink)
def duplicate_link(error):
    return jsonify(error=str(error), article=error.article), 409


@bp.errorhandler(library.ArchivedArticle)
def archived_article(error):
    return jsonify(error=str(error), article=error.article), 409


@bp.errorhandler(library.DuplicateCollection)
def duplicate_collection(error):
    return jsonify(error=str(error), collection=error.collection), 409


# ------------------------------------------------------------------ articles


@bp.get("/articles")
def list_articles():
    return jsonify(articles=get_library().list_articles(status=status_filter()))


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


@bp.post("/articles/<int:article_id>/archive")
def archive_article(article_id):
    return jsonify(get_library().archive_article(article_id))


@bp.post("/articles/<int:article_id>/restore")
def restore_article(article_id):
    return jsonify(get_library().restore_article(article_id))


@bp.get("/archive")
def list_archive():
    return jsonify(articles=get_library().list_archive(status=status_filter()))


# --------------------------------------------------------------- collections


@bp.get("/collections")
def list_collections():
    return jsonify(collections=get_library().list_collections())


@bp.post("/collections")
def create_collection():
    collection = get_library().create_collection(json_object().get("name"))
    return jsonify(collection), 201


@bp.get("/collections/<int:collection_id>")
def get_collection(collection_id):
    return jsonify(get_library().get_collection(collection_id))


@bp.get("/collections/<int:collection_id>/articles")
def list_collection_articles(collection_id):
    shelf = get_library()
    status = status_filter()
    articles = shelf.list_collection_articles(collection_id, status=status)
    return jsonify(collection=shelf.get_collection(collection_id), articles=articles)


@bp.put("/collections/<int:collection_id>/articles/<int:article_id>")
def add_to_collection(collection_id, article_id):
    return jsonify(get_library().add_to_collection(collection_id, article_id))


@bp.delete("/collections/<int:collection_id>/articles/<int:article_id>")
def remove_from_collection(collection_id, article_id):
    return jsonify(get_library().remove_from_collection(collection_id, article_id))
