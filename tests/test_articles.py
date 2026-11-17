import sqlite3
from pathlib import Path
import pytest
from reading_shelf import create_app

URL = 'https://en.wikipedia.org/wiki/Focaccia'


def test_capture_defaults_trim_and_order(client):
    first = client.post('/api/articles', json={'title': '  Focaccia ', 'url': f' {URL} '})
    assert first.status_code == 201
    assert first.json == {'id': 1, 'title': 'Focaccia', 'url': URL, 'note': '', 'status': 'to_read', 'collection_ids': [], 'archived': False}
    second = client.post('/api/articles', json={'title': 'Bread', 'url': 'https://example.com/bread'})
    assert [a['id'] for a in client.get('/api/articles').json['articles']] == [second.json['id'], 1]


def test_duplicate_preserves_identity_and_context(client, article):
    saved = client.patch(f"/api/articles/{article['id']}", json={'note': 'Try rosemary', 'status': 'reading'}).json
    duplicate = client.post('/api/articles', json={'title': 'Replacement title', 'url': URL})
    assert duplicate.status_code == 200
    assert duplicate.json == saved
    assert client.get('/api/articles').json['articles'] == [saved]


def test_restart_preserves_all_fields(app, client, article):
    saved = client.patch(f"/api/articles/{article['id']}", json={'note': 'Try rosemary', 'status': 'reading'}).json
    fresh = create_app(app.instance_path).test_client()
    assert fresh.get('/api/articles').json['articles'] == [saved]


def test_partial_edit_and_empty_note(client, article):
    url = f"/api/articles/{article['id']}"
    client.patch(url, json={'status': 'read'})
    assert client.patch(url, json={'note': '  Keep spaces\n'}).json['status'] == 'read'
    assert client.get('/api/articles').json['articles'][0]['note'] == '  Keep spaces\n'
    assert client.patch(url, json={'note': ''}).json['note'] == ''


@pytest.mark.parametrize('payload', [None, [], 'bad', {}, {'title': 'Only'}, {'url': URL}, {'title': 'x', 'url': URL, 'extra': 1}, {'title': 4, 'url': URL}, {'title': ' ', 'url': URL}, {'title': 'x'*201, 'url': URL}])
def test_bad_capture_has_no_effect(client, payload):
    response = client.post('/api/articles', json=payload)
    assert response.status_code == 400
    assert response.json['error']
    assert client.get('/api/articles').json['articles'] == []


@pytest.mark.parametrize('url', ['javascript:alert(1)', 'file:///etc/passwd', 'https://', 'https://user:pass@example.com', 'https://example.com/a b', 'https://example.com/\npath', 'https://example.com:bad', 'https://example.com:99999', 'https://[broken', 'https://example.com\\@evil.test', 'https://'+'a'*4096, 4, None])
def test_invalid_urls(client, url):
    assert client.post('/api/articles', json={'title': 'Link', 'url': url}).status_code == 400
    assert client.get('/api/articles').json['articles'] == []


@pytest.mark.parametrize('data', [{'status': 'done'}, {'status': None}, {'status': []}, {'note': 5}, {'note': 'x'*10001}, {'title': 'rename'}, {}, []])
def test_invalid_edit_is_atomic(client, article, data):
    if isinstance(data, dict) and data.get('status') == 'done':
        data['note'] = 'Must not leak through'
    response = client.patch(f"/api/articles/{article['id']}", json=data)
    assert response.status_code == 400
    assert client.get('/api/articles').json['articles'] == [article]


def test_boundaries_and_unknown_article(client, article):
    response = client.patch(f"/api/articles/{article['id']}", json={'note': 'x'*10000})
    assert response.status_code == 200
    assert client.post('/api/articles', json={'title': 'x'*200, 'url': 'https://example.com'}).status_code == 201
    assert client.patch('/api/articles/999', json={'note': 'x'}).status_code == 404
    assert client.post('/api/articles', data='{', content_type='application/json').status_code == 400


def test_sql_failure_rolls_back(app, client, article):
    with sqlite3.connect(Path(app.instance_path)/'reading-shelf.sqlite3') as connection:
        connection.execute("CREATE TRIGGER abort_edit AFTER UPDATE ON articles BEGIN SELECT RAISE(ABORT, 'simulated write failure'); END")
    response = client.patch(f"/api/articles/{article['id']}", json={'note': 'new', 'status': 'read'})
    assert response.status_code == 503
    assert 'simulated' not in response.json['error']
    assert client.get('/api/articles').json['articles'] == [article]
