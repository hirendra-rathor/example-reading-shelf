"""Article JSON operations; validation happens before each transactional write."""
from urllib.parse import urlsplit
from flask import Blueprint, jsonify, request
from werkzeug.exceptions import BadRequest, NotFound
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


def find_article(article_id):
    row = get_db().execute('SELECT * FROM articles WHERE id = ?', (article_id,)).fetchone()
    if row is None:
        raise NotFound('Article not found.')
    return dict(row)


@bp.get('/articles')
def list_articles():
    rows = get_db().execute('SELECT * FROM articles ORDER BY id DESC').fetchall()
    return jsonify(articles=[dict(row) for row in rows])


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
    return jsonify(dict(row)), 201 if inserted else 200


@bp.patch('/articles/<int:article_id>')
def edit_article(article_id):
    data = payload(('note', 'status'))
    if 'note' in data:
        data['note'] = bounded_text(data['note'], 'Note', 10000)
    if 'status' in data and data['status'] not in STATUSES:
        raise BadRequest('Status must be to_read, reading, or read.')
    connection = get_db()
    with connection:
        find_article(article_id)
        assignments = ', '.join(f'{field} = ?' for field in data)
        connection.execute(f'UPDATE articles SET {assignments} WHERE id = ?', (*data.values(), article_id))
        article = find_article(article_id)
    return jsonify(article)
