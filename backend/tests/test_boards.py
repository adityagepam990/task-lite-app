"""Board CRUD, activation and the last-board guard."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_create_board_with_default_columns(client: TestClient) -> None:
    resp = client.post("/api/boards", json={"name": "Personal"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["name"] == "Personal"
    assert body["data"]["is_active"] is True  # first board is active by default
    assert [c["name"] for c in body["data"]["columns"]] == [
        "Backlog",
        "To Do",
        "In Progress",
        "Done",
    ]
    assert body["data"]["columns"][-1]["is_done_column"] is True


def test_create_board_rejects_invalid_color(client: TestClient) -> None:
    resp = client.post("/api/boards", json={"name": "X", "color": "not-a-color"})
    assert resp.status_code == 422
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "validation_error"
    assert "color" in body["error"]["details"]["fields"]


def test_only_one_board_is_active_at_a_time(client: TestClient) -> None:
    first = client.post("/api/boards", json={"name": "First"}).json()["data"]
    second = client.post("/api/boards", json={"name": "Second", "make_active": True}).json()[
        "data"
    ]

    assert second["is_active"] is True

    listed = {b["id"]: b["is_active"] for b in client.get("/api/boards").json()["data"]}
    assert listed[first["id"]] is False
    assert listed[second["id"]] is True


def test_activate_board_switches_active_flag(client: TestClient) -> None:
    first = client.post("/api/boards", json={"name": "First"}).json()["data"]
    second = client.post("/api/boards", json={"name": "Second"}).json()["data"]

    resp = client.post(f"/api/boards/{second['id']}/activate")
    assert resp.status_code == 200
    assert resp.json()["data"]["is_active"] is True

    active = client.get("/api/boards/active").json()["data"]
    assert active["id"] == second["id"]

    listed = {b["id"]: b["is_active"] for b in client.get("/api/boards").json()["data"]}
    assert listed[first["id"]] is False


def test_update_board_partial_fields(client: TestClient) -> None:
    board = client.post("/api/boards", json={"name": "Original"}).json()["data"]

    resp = client.patch(f"/api/boards/{board['id']}", json={"description": "New desc"})
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["name"] == "Original"  # untouched
    assert body["description"] == "New desc"


def test_delete_board_cascades_and_reindexes(client: TestClient) -> None:
    a = client.post("/api/boards", json={"name": "A"}).json()["data"]
    b = client.post("/api/boards", json={"name": "B"}).json()["data"]
    client.post("/api/boards", json={"name": "C"})

    resp = client.delete(f"/api/boards/{b['id']}")
    assert resp.status_code == 200

    remaining = client.get("/api/boards").json()["data"]
    assert [r["id"] for r in remaining] == [
        board_id for board_id in [r["id"] for r in remaining] if board_id != b["id"]
    ]
    positions = [r["position"] for r in remaining]
    assert positions == sorted(positions) == list(range(len(remaining)))
    assert a["id"] in [r["id"] for r in remaining]


def test_cannot_delete_last_board(client: TestClient) -> None:
    board = client.post("/api/boards", json={"name": "Only"}).json()["data"]

    resp = client.delete(f"/api/boards/{board['id']}")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "last_board"


def test_deleting_active_board_promotes_a_neighbour(client: TestClient) -> None:
    first = client.post("/api/boards", json={"name": "First"}).json()["data"]
    client.post("/api/boards", json={"name": "Second"})

    assert first["is_active"] is True
    client.delete(f"/api/boards/{first['id']}")

    active = client.get("/api/boards/active").json()["data"]
    assert active["name"] == "Second"


def test_reorder_boards(client: TestClient) -> None:
    a = client.post("/api/boards", json={"name": "A"}).json()["data"]
    b = client.post("/api/boards", json={"name": "B"}).json()["data"]
    c = client.post("/api/boards", json={"name": "C"}).json()["data"]

    resp = client.put("/api/boards/reorder", json={"board_ids": [c["id"], a["id"], b["id"]]})
    assert resp.status_code == 200
    ordered_ids = [item["id"] for item in resp.json()["data"]]
    assert ordered_ids == [c["id"], a["id"], b["id"]]


def test_get_unknown_board_returns_404(client: TestClient) -> None:
    resp = client.get("/api/boards/999")
    assert resp.status_code == 404
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "not_found"


def test_active_board_with_no_boards_returns_404(client: TestClient) -> None:
    resp = client.get("/api/boards/active")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "no_boards"
