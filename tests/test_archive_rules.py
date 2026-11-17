"""Check the archive rules at the API boundary: read-only while archived, one link, repeatable actions."""

import pytest

from conftest import FOCACCIA_URL, file_under, make_collection, save


@pytest.fixture
def archived(client):
    focaccia = save(client)
    client.patch(f"/api/articles/{focaccia['id']}", json={"note": "Stopped at the shaping step.", "status": "reading"})
    food = make_collection(client, "Food and cooking")
    weekend = make_collection(client, "Weekend reading")
    file_under(client, food, focaccia)
    client.post(f"/api/articles/{focaccia['id']}/archive")
    return client, client.get(f"/api/articles/{focaccia['id']}").get_json(), food, weekend


@pytest.mark.parametrize("changes", [{"note": "Edited in the archive"}, {"status": "read"}, {"note": "x", "status": "to_read"}])
def test_an_archived_article_cannot_be_edited(archived, changes):
    client, focaccia, food, weekend = archived

    response = client.patch(f"/api/articles/{focaccia['id']}", json=changes)

    assert response.status_code == 409
    assert response.get_json()["error"] == "Restore this article to change it."
    assert client.get(f"/api/articles/{focaccia['id']}").get_json() == focaccia


@pytest.mark.parametrize("method", ["put", "delete"])
def test_an_archived_article_keeps_its_collections(archived, method):
    client, focaccia, food, weekend = archived

    for collection in (food, weekend):
        response = getattr(client, method)(f"/api/collections/{collection['id']}/articles/{focaccia['id']}")
        assert response.status_code == 409

    assert client.get(f"/api/articles/{focaccia['id']}").get_json()["collection_ids"] == [food["id"]]


def test_saving_an_archived_link_points_to_the_archive(archived):
    client, focaccia, food, weekend = archived

    response = client.post("/api/articles", json={"url": FOCACCIA_URL, "title": "Focaccia again"})

    assert response.status_code == 409
    body = response.get_json()
    assert body["error"] == "That link is in your archive as “Focaccia”."
    assert body["article"]["id"] == focaccia["id"]
    assert body["article"]["archived_at"] == focaccia["archived_at"]
    assert client.get("/api/articles").get_json()["articles"] == []


def test_saving_a_link_in_the_library_still_says_so(client):
    save(client)

    response = client.post("/api/articles", json={"url": FOCACCIA_URL, "title": "Focaccia again"})

    assert response.status_code == 409
    assert response.get_json()["error"] == "That link is already in your library."


def test_archive_and_restore_can_be_repeated(archived):
    client, focaccia, food, weekend = archived
    first_archived_at = focaccia["archived_at"]

    again = client.post(f"/api/articles/{focaccia['id']}/archive")
    assert again.status_code == 200
    assert again.get_json()["archived_at"] == first_archived_at

    for _ in range(2):
        restored = client.post(f"/api/articles/{focaccia['id']}/restore")
        assert restored.status_code == 200
        assert restored.get_json()["archived_at"] is None


def test_a_restored_article_can_be_edited_again(archived):
    client, focaccia, food, weekend = archived
    client.post(f"/api/articles/{focaccia['id']}/restore")

    response = client.patch(f"/api/articles/{focaccia['id']}", json={"status": "read"})

    assert response.status_code == 200
    assert response.get_json()["status"] == "read"


@pytest.mark.parametrize("action", ["archive", "restore"])
def test_unknown_articles_are_not_found(client, action):
    response = client.post(f"/api/articles/999/{action}")

    assert response.status_code == 404


def test_the_archive_status_filter_must_name_a_status(client):
    assert client.get("/api/archive?status=done").status_code == 400


def test_an_archived_article_can_still_be_opened_by_id(archived):
    client, focaccia, food, weekend = archived

    article = client.get(f"/api/articles/{focaccia['id']}").get_json()

    assert article["url"] == FOCACCIA_URL
    assert article["archived_at"]
