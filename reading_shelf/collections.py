"""Collections group article identities; reading context stays on the article."""
from flask import Blueprint, jsonify, request
from werkzeug.exceptions import NotFound
from .articles import bounded_text, find_article, payload
from .db import get_db

bp = Blueprint('collections', __name__, url_prefix='/api')


def find_collection(collection_id):
    if not 0 < collection_id <= 2**63 - 1:
        raise NotFound('Collection not found.')
    row = get_db().execute('SELECT id, name FROM collections WHERE id = ?', (collection_id,)).fetchone()
    if row is None:
        raise NotFound('Collection not found.')
    return dict(row)


@bp.get('/collections')
def list_collections():
    return jsonify(collections=[dict(row) for row in get_db().execute('SELECT id, name FROM collections ORDER BY name_key, id')])


@bp.post('/collections')
def create_collection():
    data = payload(('name',), ('name',))
    name = bounded_text(data['name'], 'Name', 100, trim=True, required=True)
    connection = get_db()
    with connection:
        inserted = connection.execute(
            'INSERT INTO collections (name, name_key) VALUES (?, ?) ON CONFLICT(name_key) DO NOTHING',
            (name, name.casefold()),
        ).rowcount
        row = connection.execute('SELECT id, name FROM collections WHERE name_key = ?', (name.casefold(),)).fetchone()
    return jsonify(dict(row)), 201 if inserted else 200


@bp.route('/collections/<int:collection_id>/articles/<int:article_id>', methods=['PUT', 'DELETE'])
def change_membership(collection_id, article_id):
    connection = get_db()
    with connection:
        find_collection(collection_id)
        find_article(article_id)
        if request.method == 'PUT':
            connection.execute('INSERT INTO collection_articles VALUES (?, ?) ON CONFLICT DO NOTHING', (collection_id, article_id))
        else:
            connection.execute('DELETE FROM collection_articles WHERE collection_id = ? AND article_id = ?', (collection_id, article_id))
        result = find_article(article_id)
    return jsonify(result)
