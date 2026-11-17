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
