"""Article JSON operations; validation happens before each transactional write."""
import re
from urllib.parse import urlsplit
from flask import Blueprint, jsonify, request
from werkzeug.exceptions import BadRequest, Conflict, NotFound
from .db import get_db

bp = Blueprint('articles', __name__, url_prefix='/api')
STATUSES = ('to_read', 'reading', 'read')


def payload(allowed, required=()):
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data or set(data) - set(allowed) or set(required) - set(data):
        raise BadRequest('Send a JSON object with the required fields and no unknown fields.')
    return data


def bounded_text(value, name, maximum, *, trim=False, required=False):
    if not isinstance(value, str):
        raise BadRequest(f'{name} must be text.')
    value = value.strip() if trim else value
    if len(value) > maximum or (required and not value):
        raise BadRequest(f'{name} must contain {"1" if required else "0"}–{maximum} characters.')
    return value


def article_url(value):
    value = bounded_text(value, 'URL', 4096, trim=True, required=True)
    try:
        parsed = urlsplit(value)
        valid = (parsed.scheme in ('http', 'https') and parsed.hostname
                 and parsed.username is None and parsed.password is None)
        parsed.port  # Also rejects malformed/out-of-range ports.
    except ValueError:
        valid = False
    if not valid or any(c.isspace() or ord(c) < 32 or ord(c) == 127 or c == '\\' for c in value):
        raise BadRequest('URL must be an HTTP(S) link with a hostname and no whitespace or credentials.')
    return value


def serialize_article(row):
    article = dict(row)
    article['archived'] = bool(article['archived'])
    article['collection_ids'] = [r[0] for r in get_db().execute(
        'SELECT collection_id FROM collection_articles WHERE article_id = ? ORDER BY collection_id', (row['id'],)
    )]
    return article


def find_article(article_id):
    if not 0 < article_id <= 2**63 - 1:
        raise NotFound('Article not found.')
    row = get_db().execute('SELECT * FROM articles WHERE id = ?', (article_id,)).fetchone()
    if row is None:
        raise NotFound('Article not found.')
    return serialize_article(row)


@bp.get('/articles')
def list_articles():
    from .collections import find_collection
    allowed = {'collection_id', 'status', 'view'}
    if set(request.args) - allowed or any(len(request.args.getlist(k)) != 1 for k in request.args):
        raise BadRequest('Use each supported filter once: collection_id, status, view.')
    view = request.args.get('view', 'active')
    if view not in ('active', 'archive'):
        raise BadRequest('View must be active or archive.')
    clauses, values = ['a.archived = ?'], [int(view == 'archive')]
    if 'collection_id' in request.args:
        value = request.args['collection_id']
        if not re.fullmatch(r'[1-9][0-9]{0,18}', value) or int(value) > 2**63 - 1:
            raise BadRequest('Collection ID must be a positive integer.')
        find_collection(int(value))
        clauses.append('EXISTS (SELECT 1 FROM collection_articles m WHERE m.article_id = a.id AND m.collection_id = ?)')
        values.append(int(value))
    if 'status' in request.args:
        if request.args['status'] not in STATUSES:
            raise BadRequest('Status must be to_read, reading, or read.')
        clauses.append('a.status = ?')
        values.append(request.args['status'])
    where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
    rows = get_db().execute('SELECT a.* FROM articles a' + where + ' ORDER BY a.id DESC', values).fetchall()
    return jsonify(articles=[serialize_article(row) for row in rows])


@bp.post('/articles')
def capture_article():
    data = payload(('title', 'url'), ('title', 'url'))
    title = bounded_text(data['title'], 'Title', 200, trim=True, required=True)
    url = article_url(data['url'])
    connection = get_db()
    with connection:
        inserted = connection.execute(
            'INSERT INTO articles (title, url) VALUES (?, ?) ON CONFLICT(url) DO NOTHING', (title, url)
        ).rowcount
        row = connection.execute('SELECT * FROM articles WHERE url = ?', (url,)).fetchone()
    return jsonify(serialize_article(row)), 201 if inserted else 200


@bp.patch('/articles/<int:article_id>')
def edit_article(article_id):
    data = payload(('note', 'status'))
    if 'note' in data:
        data['note'] = bounded_text(data['note'], 'Note', 10000)
    if 'status' in data and data['status'] not in STATUSES:
        raise BadRequest('Status must be to_read, reading, or read.')
    connection = get_db()
    with connection:
        connection.execute('BEGIN IMMEDIATE')
        if find_article(article_id)['archived']:
            raise Conflict('Restore this article before editing its reading context.')
        assignments = ', '.join(f'{field} = ?' for field in data)
        connection.execute(f'UPDATE articles SET {assignments} WHERE id = ?', (*data.values(), article_id))
        article = find_article(article_id)
    return jsonify(article)


@bp.route('/articles/<int:article_id>/archive', methods=['PUT', 'DELETE'])
def change_archive(article_id):
    connection = get_db()
    with connection:
        connection.execute('BEGIN IMMEDIATE')
        find_article(article_id)
        connection.execute('UPDATE articles SET archived = ? WHERE id = ?', (int(request.method == 'PUT'), article_id))
        result = find_article(article_id)
    return jsonify(result)
