"""Column CRUD, reordering, and the last-column guard."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _board(client: TestClient) -> dict:
    return client.post("/api/boards", json={"name": "Board", "with_default_columns": False}).json()[
        "data"
    ]


def test_create_column_appends(client: TestClient) -> None:
    board = _board(client)

    first = client.post(f"/api/boards/{board['id']}/columns", json={"name": "To Do"}).json()["data"]
    second = client.post(f"/api/boards/{board['id']}/columns", json={"name": "Done"}).json()["data"]

    assert first["position"] == 0
    assert second["position"] == 1


def test_create_column_at_explicit_position(client: TestClient) -> None:
    board = _board(client)
    a = client.post(f"/api/boards/{board['id']}/columns", json={"name": "A"}).json()["data"]
    client.post(f"/api/boards/{board['id']}/columns", json={"name": "B"}).json()

    inserted = client.post(
        f"/api/boards/{board['id']}/columns", json={"name": "Inserted", "position": 0}
    ).json()["data"]

    columns = client.get(f"/api/boards/{board['id']}/columns").json()["data"]
    names_in_order = [c["name"] for c in columns]
    assert names_in_order[0] == "Inserted"
    assert inserted["position"] == 0
    assert a["id"] in {c["id"] for c in columns}


def test_toggle_done_column_restamps_existing_tasks(client: TestClient) -> None:
    board = _board(client)
    column = client.post(f"/api/boards/{board['id']}/columns", json={"name": "Lane"}).json()["data"]
    task = client.post(f"/api/columns/{column['id']}/tasks", json={"title": "Card"}).json()["data"]
    assert task["is_completed"] is False

    resp = client.patch(f"/api/columns/{column['id']}", json={"is_done_column": True})
    assert resp.status_code == 200
    restamped_tasks = resp.json()["data"]["tasks"]
    assert restamped_tasks[0]["is_completed"] is True
    assert restamped_tasks[0]["completed_at"] is not None

    # Flip back: completion should clear.
    resp2 = client.patch(f"/api/columns/{column['id']}", json={"is_done_column": False})
    assert resp2.json()["data"]["tasks"][0]["is_completed"] is False
    assert resp2.json()["data"]["tasks"][0]["completed_at"] is None


def test_delete_column_reindexes_siblings(client: TestClient) -> None:
    board = _board(client)
    a = client.post(f"/api/boards/{board['id']}/columns", json={"name": "A"}).json()["data"]
    b = client.post(f"/api/boards/{board['id']}/columns", json={"name": "B"}).json()["data"]
    c = client.post(f"/api/boards/{board['id']}/columns", json={"name": "C"}).json()["data"]

    client.delete(f"/api/columns/{b['id']}")

    remaining = client.get(f"/api/boards/{board['id']}/columns").json()["data"]
    assert [r["id"] for r in remaining] == [a["id"], c["id"]]
    assert [r["position"] for r in remaining] == [0, 1]


def test_cannot_delete_last_column(client: TestClient) -> None:
    board = _board(client)
    column = client.post(f"/api/boards/{board['id']}/columns", json={"name": "Only"}).json()["data"]

    resp = client.delete(f"/api/columns/{column['id']}")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "last_column"


def test_reorder_columns(client: TestClient) -> None:
    board = _board(client)
    a = client.post(f"/api/boards/{board['id']}/columns", json={"name": "A"}).json()["data"]
    b = client.post(f"/api/boards/{board['id']}/columns", json={"name": "B"}).json()["data"]
    c = client.post(f"/api/boards/{board['id']}/columns", json={"name": "C"}).json()["data"]

    resp = client.put(
        f"/api/boards/{board['id']}/columns/reorder",
        json={"column_ids": [c["id"], a["id"], b["id"]]},
    )
    assert resp.status_code == 200
    assert [item["id"] for item in resp.json()["data"]] == [c["id"], a["id"], b["id"]]
