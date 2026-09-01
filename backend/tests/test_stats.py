"""Statistics aggregation."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_stats_counts_open_and_completed(client: TestClient) -> None:
    board = client.post("/api/boards", json={"name": "Board"}).json()["data"]
    columns = client.get(f"/api/boards/{board['id']}/columns").json()["data"]
    todo = next(c for c in columns if c["name"] == "To Do")
    done = next(c for c in columns if c["is_done_column"])

    client.post(f"/api/columns/{todo['id']}/tasks", json={"title": "Open 1", "priority": "high"})
    client.post(f"/api/columns/{todo['id']}/tasks", json={"title": "Open 2", "priority": "low"})
    task = client.post(f"/api/columns/{todo['id']}/tasks", json={"title": "To finish"}).json()["data"]
    client.post(f"/api/tasks/{task['id']}/move", json={"column_id": done["id"], "position": 0})

    stats = client.get(f"/api/boards/{board['id']}/stats").json()["data"]
    assert stats["total_tasks"] == 3
    assert stats["open_tasks"] == 2
    assert stats["completed_tasks"] == 1
    assert stats["completed_this_week"] == 1
    assert stats["by_priority"]["high"] == 1
    assert stats["by_priority"]["low"] == 1
    assert len(stats["completion_trend"]) == 7
    assert stats["completion_trend"][-1]["count"] == 1  # completed today


def test_stats_follows_active_board(client: TestClient) -> None:
    board_a = client.post("/api/boards", json={"name": "A", "make_active": True}).json()["data"]
    client.post("/api/boards", json={"name": "B"})

    columns = client.get(f"/api/boards/{board_a['id']}/columns").json()["data"]
    client.post(f"/api/columns/{columns[0]['id']}/tasks", json={"title": "Task"})

    stats = client.get("/api/stats").json()["data"]
    assert stats["board_id"] == board_a["id"]
    assert stats["total_tasks"] == 1


def test_stats_overdue_and_due_soon(client: TestClient) -> None:
    board = client.post("/api/boards", json={"name": "Board"}).json()["data"]
    columns = client.get(f"/api/boards/{board['id']}/columns").json()["data"]
    todo = columns[0]

    client.post(
        f"/api/columns/{todo['id']}/tasks",
        json={"title": "Overdue", "due_date": "2000-01-01T00:00:00Z"},
    )
    client.post(
        f"/api/columns/{todo['id']}/tasks",
        json={"title": "Due soon", "due_date": "2100-01-01T00:00:00Z"},
    )

    stats = client.get(f"/api/boards/{board['id']}/stats").json()["data"]
    assert stats["overdue_tasks"] == 1
