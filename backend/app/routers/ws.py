"""WebSocket endpoint for real-time board updates.

Clients connect to ``ws://localhost:8000/ws`` and receive every change as it
happens. Pass ``?board_id=N`` to only receive events for one board.

Message shape, matching ``RealtimeEvent`` in ``frontend/src/types/api.ts``:

    {"event": "task.moved", "board_id": 1, "data": {...}}

The connection is receive-driven: we await incoming frames purely to notice
disconnects. Clients may send ``{"type": "ping"}`` and will get a ``pong`` back,
which is how the frontend distinguishes a live socket from a half-open one.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.realtime import manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    board_id: int | None = Query(
        default=None,
        description="Only receive events for this board. Omit for all boards.",
    ),
) -> None:
    """Register a client and keep the socket open until it goes away."""
    connection = await manager.connect(websocket, board_id=board_id)

    # Tell the client it is live, and confirm which scope it got. Useful when
    # debugging a client that thinks it subscribed to a different board.
    await websocket.send_json(
        {"event": "connected", "board_id": board_id, "data": {"scope": board_id or "all"}}
    )

    try:
        while True:
            # We do not expect meaningful client messages; this await is how a
            # disconnect surfaces. Anything that is not a ping is ignored rather
            # than treated as an error, so a chatty client cannot drop its own
            # subscription.
            message = await websocket.receive_json()
            if isinstance(message, dict) and message.get("type") == "ping":
                await websocket.send_json({"event": "pong", "board_id": board_id, "data": None})
    except WebSocketDisconnect:
        logger.debug("client disconnected from /ws")
    except Exception:  # noqa: BLE001 - a malformed frame should not spam logs
        logger.debug("closing /ws after an unexpected frame", exc_info=True)
    finally:
        await manager.disconnect(connection)
