"""Check the collection-name, membership, and status-filter rules at the API boundary."""

import pytest

from conftest import make_collection, save


def collection_names(client):
    return [c["name"] for c in client.get("/api/collections").get_json()["collections"]]


@pytest.mark.parametrize("name", ["", "   ", None, 7, ["Food"], "x" * 81])
def test_collection_names_must_be_present_and_reasonable(client, name):
    response = client.post("/api/collections", json={"name": name})

    assert response.status_code == 400
    assert response.get_json()["error"]
    assert collection_names(client) == []


def test_collection_names_are_tidied(client):
    created = make_collection(client, "  Food   and\tcooking ")

    assert created["name"] == "Food and cooking"
    assert created["article_count"] == 0


@pytest.mark.parametrize("again", ["Food and cooking", "food and cooking", " food AND  cooking ", "FOOD AND COOKING"])
def test_a_name_already_in_use_is_refused_ignoring_case_and_spacing(client, again):
    original = make_collection(client, "Food and cooking")

    response = client.post("/api/collections", json={"name": again})

    assert response.status_code == 409
    body = response.get_json()
    assert body["error"] == "You already have a collection called “Food and cooking”."
    assert body["collection"]["id"] == original["id"]
    assert collection_names(client) == ["Food and cooking"]


def test_unknown_collections_and_articles_are_not_found(client):
    article = save(client)
    food = make_collection(client, "Food and cooking")

    assert client.get("/api/collections/999").status_code == 404
    assert client.get("/api/collections/999/articles").status_code == 404
    for method in ("put", "delete"):
        call = getattr(client, method)
        assert call(f"/api/collections/999/articles/{article['id']}").status_code == 404
        assert call(f"/api/collections/{food['id']}/articles/999").status_code == 404
    assert client.get(f"/api/articles/{article['id']}").get_json()["collection_ids"] == []


@pytest.mark.parametrize("status", ["done", "Reading", "READ"])
def test_status_filters_must_name_a_status(client, status):
    food = make_collection(client, "Food and cooking")

    assert client.get(f"/api/articles?status={status}").status_code == 400
    assert client.get(f"/api/collections/{food['id']}/articles?status={status}").status_code == 400


def test_an_empty_status_filter_means_every_status(client):
    save(client)

    assert len(client.get("/api/articles?status=").get_json()["articles"]) == 1


def test_collection_requests_must_send_a_json_object(client):
    response = client.post("/api/collections", data="Food", content_type="application/json")

    assert response.status_code == 400
