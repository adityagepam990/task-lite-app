"""Task CRUD, moving between columns, reordering, and search/filter."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _board_with_columns(client: TestClient) -> tuple[dict, dict, dict]:
    """Create a board with two plain columns and one done column."""
    board = client.post("/api/boards", json={"name": "Board", "with_default_columns": False}).json()[
        "data"
    ]
    todo = client.post(f"/api/boards/{board['id']}/columns", json={"name": "To Do"}).json()["data"]
    doing = client.post(f"/api/boards/{board['id']}/columns", json={"name": "Doing"}).json()["data"]
    done = client.post(
        f"/api/boards/{board['id']}/columns", json={"name": "Done", "is_done_column": True}
    ).json()["data"]
    return todo, doing, done


def test_create_task_defaults_and_normalises_tags(client: TestClient) -> None:
    todo, _doing, _done = _board_with_columns(client)

    resp = client.post(
        f"/api/columns/{todo['id']}/tasks",
        json={"title": "  Buy milk  ", "tags": ["Errand", " errand ", "Home"]},
    )
    assert resp.status_code == 201
    body = resp.json()["data"]
    assert body["title"] == "Buy milk"
    assert body["priority"] == "medium"
    assert body["tags"] == ["errand", "home"]  # trimmed, lowercased, de-duplicated
    assert body["is_completed"] is False


def test_create_task_rejects_blank_title(client: TestClient) -> None:
    todo, _doing, _done = _board_with_columns(client)

    resp = client.post(f"/api/columns/{todo['id']}/tasks", json={"title": "   "})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


def test_flat_create_requires_column_id(client: TestClient) -> None:
    resp = client.post("/api/tasks", json={"title": "Orphan"})
    assert resp.status_code == 422
    assert resp.json()["error"]["details"]["field"] == "column_id"


def test_flat_create_with_column_id_works(client: TestClient) -> None:
    todo, _doing, _done = _board_with_columns(client)

    resp = client.post("/api/tasks", json={"title": "Via flat route", "column_id": todo["id"]})
    assert resp.status_code == 201
    assert resp.json()["data"]["column_id"] == todo["id"]


def test_update_task_partial_and_clear_due_date(client: TestClient) -> None:
    todo, _doing, _done = _board_with_columns(client)
    task = client.post(
        f"/api/columns/{todo['id']}/tasks",
        json={"title": "Card", "due_date": "2026-01-01T00:00:00Z"},
    ).json()["data"]

    resp = client.patch(f"/api/tasks/{task['id']}", json={"priority": "high"})
    assert resp.json()["data"]["priority"] == "high"
    assert resp.json()["data"]["due_date"] is not None  # untouched by omission

    resp2 = client.patch(f"/api/tasks/{task['id']}", json={"due_date": None})
    assert resp2.json()["data"]["due_date"] is None  # explicit null clears it


def test_update_task_rejects_unknown_field(client: TestClient) -> None:
    todo, _doing, _done = _board_with_columns(client)
    task = client.post(f"/api/columns/{todo['id']}/tasks", json={"title": "Card"}).json()["data"]

    resp = client.patch(f"/api/tasks/{task['id']}", json={"column_id": 999})
    assert resp.status_code == 422  # extra="forbid": column moves go through /move


def test_move_task_within_same_column_reorders(client: TestClient) -> None:
    todo, _doing, _done = _board_with_columns(client)
    a = client.post(f"/api/columns/{todo['id']}/tasks", json={"title": "A"}).json()["data"]
    b = client.post(f"/api/columns/{todo['id']}/tasks", json={"title": "B"}).json()["data"]
    c = client.post(f"/api/columns/{todo['id']}/tasks", json={"title": "C"}).json()["data"]

    resp = client.post(f"/api/tasks/{c['id']}/move", json={"column_id": todo["id"], "position": 0})
    assert resp.status_code == 200
    assert resp.json()["data"]["position"] == 0

    ordered = client.get(f"/api/columns/{todo['id']}/tasks").json()["data"]
    assert [t["id"] for t in ordered] == [c["id"], a["id"], b["id"]]
    assert [t["position"] for t in ordered] == [0, 1, 2]


def test_move_task_across_columns_updates_both_lanes(client: TestClient) -> None:
    todo, doing, _done = _board_with_columns(client)
    a = client.post(f"/api/columns/{todo['id']}/tasks", json={"title": "A"}).json()["data"]
    b = client.post(f"/api/columns/{todo['id']}/tasks", json={"title": "B"}).json()["data"]

    resp = client.post(f"/api/tasks/{a['id']}/move", json={"column_id": doing["id"], "position": 0})
    assert resp.status_code == 200
    assert resp.json()["data"]["column_id"] == doing["id"]

    todo_tasks = client.get(f"/api/columns/{todo['id']}/tasks").json()["data"]
    doing_tasks = client.get(f"/api/columns/{doing['id']}/tasks").json()["data"]
    assert [t["id"] for t in todo_tasks] == [b["id"]]
    assert todo_tasks[0]["position"] == 0  # gap closed
    assert [t["id"] for t in doing_tasks] == [a["id"]]


def test_move_task_into_done_column_marks_completed(client: TestClient) -> None:
    todo, _doing, done = _board_with_columns(client)
    task = client.post(f"/api/columns/{todo['id']}/tasks", json={"title": "Card"}).json()["data"]

    resp = client.post(f"/api/tasks/{task['id']}/move", json={"column_id": done["id"], "position": 0})
    body = resp.json()["data"]
    assert body["is_completed"] is True
    assert body["completed_at"] is not None

    back = client.post(f"/api/tasks/{task['id']}/move", json={"column_id": todo["id"], "position": 0})
    assert back.json()["data"]["is_completed"] is False
    assert back.json()["data"]["completed_at"] is None


def test_move_task_clamps_out_of_range_position(client: TestClient) -> None:
    todo, _doing, _done = _board_with_columns(client)
    task = client.post(f"/api/columns/{todo['id']}/tasks", json={"title": "Card"}).json()["data"]

    resp = client.post(f"/api/tasks/{task['id']}/move", json={"column_id": todo["id"], "position": 999})
    assert resp.status_code == 200  # clamped, not rejected
    assert resp.json()["data"]["position"] == 0  # only card in the column


def test_move_task_across_boards_is_rejected(client: TestClient) -> None:
    todo, _doing, _done = _board_with_columns(client)
    other_board = client.post(
        "/api/boards", json={"name": "Other", "with_default_columns": False}
    ).json()["data"]
    other_column = client.post(
        f"/api/boards/{other_board['id']}/columns", json={"name": "Lane"}
    ).json()["data"]

    task = client.post(f"/api/columns/{todo['id']}/tasks", json={"title": "Card"}).json()["data"]

    resp = client.post(
        f"/api/tasks/{task['id']}/move", json={"column_id": other_column["id"], "position": 0}
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


def test_delete_task_closes_gap(client: TestClient) -> None:
    todo, _doing, _done = _board_with_columns(client)
    a = client.post(f"/api/columns/{todo['id']}/tasks", json={"title": "A"}).json()["data"]
    b = client.post(f"/api/columns/{todo['id']}/tasks", json={"title": "B"}).json()["data"]

    client.delete(f"/api/tasks/{a['id']}")

    remaining = client.get(f"/api/columns/{todo['id']}/tasks").json()["data"]
    assert [t["id"] for t in remaining] == [b["id"]]
    assert remaining[0]["position"] == 0


def test_reorder_tasks_explicit_order(client: TestClient) -> None:
    todo, _doing, _done = _board_with_columns(client)
    a = client.post(f"/api/columns/{todo['id']}/tasks", json={"title": "A"}).json()["data"]
    b = client.post(f"/api/columns/{todo['id']}/tasks", json={"title": "B"}).json()["data"]
    c = client.post(f"/api/columns/{todo['id']}/tasks", json={"title": "C"}).json()["data"]

    resp = client.put(
        f"/api/columns/{todo['id']}/tasks/reorder",
        json={"task_ids": [c["id"], b["id"], a["id"]]},
    )
    assert resp.status_code == 200
    assert [t["id"] for t in resp.json()["data"]] == [c["id"], b["id"], a["id"]]


def test_search_by_priority_and_query(client: TestClient) -> None:
    todo, _doing, _done = _board_with_columns(client)
    client.post(f"/api/columns/{todo['id']}/tasks", json={"title": "Urgent fix", "priority": "high"})
    client.post(f"/api/columns/{todo['id']}/tasks", json={"title": "Low key task", "priority": "low"})

    high_only = client.get("/api/tasks", params={"priority": "high"}).json()["data"]
    assert len(high_only) == 1
    assert high_only[0]["title"] == "Urgent fix"

    by_query = client.get("/api/tasks", params={"q": "low key"}).json()["data"]
    assert len(by_query) == 1
    assert by_query[0]["title"] == "Low key task"


def test_search_sorts_by_priority_desc(client: TestClient) -> None:
    todo, _doing, _done = _board_with_columns(client)
    client.post(f"/api/columns/{todo['id']}/tasks", json={"title": "Low", "priority": "low"})
    client.post(f"/api/columns/{todo['id']}/tasks", json={"title": "High", "priority": "high"})
    client.post(f"/api/columns/{todo['id']}/tasks", json={"title": "Medium", "priority": "medium"})

    results = client.get("/api/tasks").json()["data"]
    assert [t["priority"] for t in results] == ["high", "medium", "low"]


def test_search_by_tag(client: TestClient) -> None:
    todo, _doing, _done = _board_with_columns(client)
    client.post(f"/api/columns/{todo['id']}/tasks", json={"title": "A", "tags": ["work"]})
    client.post(f"/api/columns/{todo['id']}/tasks", json={"title": "B", "tags": ["home"]})

    results = client.get("/api/tasks", params={"tag": "work"}).json()["data"]
    assert [t["title"] for t in results] == ["A"]


def test_board_tags_endpoint(client: TestClient) -> None:
    board = client.post("/api/boards", json={"name": "Board"}).json()["data"]
    columns = client.get(f"/api/boards/{board['id']}/columns").json()["data"]
    client.post(f"/api/columns/{columns[0]['id']}/tasks", json={"title": "A", "tags": ["x", "y"]})
    client.post(f"/api/columns/{columns[0]['id']}/tasks", json={"title": "B", "tags": ["x"]})

    tags = client.get(f"/api/boards/{board['id']}/tags").json()["data"]
    assert tags[0] == "x"  # most frequent first
    assert set(tags) == {"x", "y"}
