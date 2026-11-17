import pytest
from reading_shelf import create_app

@pytest.fixture
def app(tmp_path):
    result = create_app(str(tmp_path / 'library'))
    result.config['TESTING'] = True
    return result

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def article(client):
    return client.post('/api/articles', json={'title': 'Focaccia', 'url': 'https://en.wikipedia.org/wiki/Focaccia'}).get_json()
