"""One shared article in two collections: notes, status filters, and removal through the API."""

import pytest

from conftest import (
    FOCACCIA_URL,
    collection_articles,
    file_under,
    library_articles,
    make_collection,
    save,
)


@pytest.fixture
def shelf(client):
    """Focaccia, marked Reading with a note, in "Food and cooking" and "Weekend reading"."""
    focaccia = save(client)
    client.patch(f"/api/articles/{focaccia['id']}", json={"note": "Try rosemary on top.", "status": "reading"})
    food = make_collection(client, "Food and cooking")
    weekend = make_collection(client, "Weekend reading")
    file_under(client, food, focaccia)
    file_under(client, weekend, focaccia)
    return client, focaccia, food, weekend


def test_an_article_can_be_in_two_collections(shelf):
    client, focaccia, food, weekend = shelf

    assert [a["id"] for a in collection_articles(client, food)] == [focaccia["id"]]
    assert [a["id"] for a in collection_articles(client, weekend)] == [focaccia["id"]]
    assert library_articles(client)[0]["collection_ids"] == sorted([food["id"], weekend["id"]])

    counts = {c["name"]: c["article_count"] for c in client.get("/api/collections").get_json()["collections"]}
    assert counts == {"Food and cooking": 1, "Weekend reading": 1}


def test_a_note_edited_from_one_collection_shows_in_the_other(shelf):
    client, focaccia, food, weekend = shelf
    opened_from_food = collection_articles(client, food)[0]

    client.patch(f"/api/articles/{opened_from_food['id']}", json={"note": "Stopped at the shaping step."})

    opened_from_weekend = collection_articles(client, weekend)[0]
    assert opened_from_weekend["id"] == focaccia["id"]
    assert opened_from_weekend["note"] == "Stopped at the shaping step."
    assert library_articles(client)[0]["note"] == "Stopped at the shaping step."


def test_reading_lists_cover_the_library_and_each_collection(shelf):
    client, focaccia, food, weekend = shelf
    sourdough = save(client, "https://en.wikipedia.org/wiki/Sourdough", "Sourdough")
    file_under(client, weekend, sourdough)

    assert [a["title"] for a in library_articles(client, "reading")] == ["Focaccia"]
    assert [a["title"] for a in library_articles(client, "to_read")] == ["Sourdough"]
    assert [a["title"] for a in collection_articles(client, weekend, "reading")] == ["Focaccia"]
    assert [a["title"] for a in collection_articles(client, weekend)] == ["Sourdough", "Focaccia"]
    assert [a["title"] for a in collection_articles(client, food, "reading")] == ["Focaccia"]


def test_marking_read_in_one_collection_drops_it_from_every_reading_list(shelf):
    client, focaccia, food, weekend = shelf
    in_weekend = collection_articles(client, weekend)[0]

    client.patch(f"/api/articles/{in_weekend['id']}", json={"status": "read"})

    assert collection_articles(client, food, "reading") == []
    assert collection_articles(client, weekend, "reading") == []
    assert library_articles(client, "reading") == []
    assert [a["id"] for a in collection_articles(client, food, "read")] == [focaccia["id"]]


def test_removing_from_one_collection_keeps_it_elsewhere(shelf):
    client, focaccia, food, weekend = shelf

    response = client.delete(f"/api/collections/{food['id']}/articles/{focaccia['id']}")

    assert response.status_code == 200
    assert response.get_json()["collection_ids"] == [weekend["id"]]
    assert collection_articles(client, food) == []
    remaining = collection_articles(client, weekend)
    assert [a["id"] for a in remaining] == [focaccia["id"]]
    assert remaining[0]["note"] == "Try rosemary on top."
    assert remaining[0]["status"] == "reading"
    in_library = library_articles(client)
    assert [a["url"] for a in in_library] == [FOCACCIA_URL]


def test_adding_and_removing_twice_changes_nothing_more(shelf):
    client, focaccia, food, weekend = shelf

    again = client.put(f"/api/collections/{food['id']}/articles/{focaccia['id']}")
    assert again.status_code == 200
    assert len(collection_articles(client, food)) == 1

    for _ in range(2):
        removed = client.delete(f"/api/collections/{food['id']}/articles/{focaccia['id']}")
        assert removed.status_code == 200
    assert collection_articles(client, food) == []
    assert len(collection_articles(client, weekend)) == 1


def test_collections_and_memberships_survive_a_restart(shelf, restart):
    client, focaccia, food, weekend = shelf
    client.delete(f"/api/collections/{food['id']}/articles/{focaccia['id']}")

    after = restart()

    names = [c["name"] for c in after.get("/api/collections").get_json()["collections"]]
    assert names == ["Food and cooking", "Weekend reading"]
    assert collection_articles(after, food) == []
    kept = collection_articles(after, weekend, "reading")
    assert [(a["id"], a["note"]) for a in kept] == [(focaccia["id"], "Try rosemary on top.")]


def test_collections_are_listed_by_name(client):
    for name in ("Weekend reading", "art history", "Food and cooking"):
        make_collection(client, name)

    names = [c["name"] for c in client.get("/api/collections").get_json()["collections"]]

    assert names == ["art history", "Food and cooking", "Weekend reading"]


def test_page_offers_collections_and_a_status_filter(client):
    page = client.get("/").get_data(as_text=True)

    assert '<form id="collection-form"' in page
    assert 'id="view-list"' in page
    for value in ("", "to_read", "reading", "read"):
        assert f'data-filter="{value}"' in page
    assert 'class="add-to-collection"' in page
