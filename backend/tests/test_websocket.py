"""Real-time event broadcasting over the /ws endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_websocket_connect_sends_confirmation(client: TestClient) -> None:
    with client.websocket_connect("/ws?board_id=1") as ws:
        message = ws.receive_json()
        assert message["event"] == "connected"
        assert message["board_id"] == 1


def test_websocket_ping_pong(client: TestClient) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()  # connected
        ws.send_json({"type": "ping"})
        pong = ws.receive_json()
        assert pong["event"] == "pong"


def test_task_move_broadcasts_to_subscribed_board(client: TestClient) -> None:
    board = client.post("/api/boards", json={"name": "Board"}).json()["data"]
    columns = client.get(f"/api/boards/{board['id']}/columns").json()["data"]
    todo, doing = columns[0], columns[1]
    task = client.post(f"/api/columns/{todo['id']}/tasks", json={"title": "Card"}).json()["data"]

    with client.websocket_connect(f"/ws?board_id={board['id']}") as ws:
        ws.receive_json()  # connected

        client.post(f"/api/tasks/{task['id']}/move", json={"column_id": doing["id"], "position": 0})

        event = ws.receive_json()
        assert event["event"] == "task.moved"
        assert event["board_id"] == board["id"]
        assert event["data"]["to_column_id"] == doing["id"]


def test_events_do_not_leak_to_other_boards(client: TestClient) -> None:
    board_a = client.post("/api/boards", json={"name": "A"}).json()["data"]
    board_b = client.post("/api/boards", json={"name": "B"}).json()["data"]
    columns_a = client.get(f"/api/boards/{board_a['id']}/columns").json()["data"]

    with client.websocket_connect(f"/ws?board_id={board_b['id']}") as ws:
        ws.receive_json()  # connected

        client.post(f"/api/columns/{columns_a[0]['id']}/tasks", json={"title": "Card"})

        # No event should arrive for board B; confirm the socket is still alive by
        # pinging it instead of blocking forever on receive.
        ws.send_json({"type": "ping"})
        message = ws.receive_json()
        assert message["event"] == "pong"
