"""Shared fixtures: each test gets its own instance folder with a real SQLite library."""

import pytest

from reading_shelf import create_app

FOCACCIA_URL = "https://en.wikipedia.org/wiki/Focaccia"


@pytest.fixture
def instance_path(tmp_path):
    return str(tmp_path / "instance")


@pytest.fixture
def client(instance_path):
    return create_app(instance_path).test_client()


@pytest.fixture
def restart(instance_path):
    """Start a fresh application on the same instance folder, as a server restart would."""

    def _restart():
        return create_app(instance_path).test_client()

    return _restart


def save(client, url=FOCACCIA_URL, title="Focaccia"):
    response = client.post("/api/articles", json={"url": url, "title": title})
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def make_collection(client, name):
    response = client.post("/api/collections", json={"name": name})
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def file_under(client, collection, article):
    response = client.put(f"/api/collections/{collection['id']}/articles/{article['id']}")
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def collection_articles(client, collection, status=None):
    query = f"?status={status}" if status else ""
    response = client.get(f"/api/collections/{collection['id']}/articles{query}")
    assert response.status_code == 200, response.get_json()
    return response.get_json()["articles"]


def library_articles(client, status=None):
    query = f"?status={status}" if status else ""
    response = client.get(f"/api/articles{query}")
    assert response.status_code == 200, response.get_json()
    return response.get_json()["articles"]
