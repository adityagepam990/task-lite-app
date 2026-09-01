"""WebSocket connection registry and event fan-out.

Clients connect to ``/ws`` (optionally scoped to one board with ``?board_id=``)
and receive a JSON event whenever data changes. This is what makes a card that
you drag on your phone move on your tablet a moment later.

Design notes:

* Connections are held in memory. A single-process personal app needs nothing
  more; scaling past one worker would mean an external pub/sub instead.
* Broadcasting never raises. A dead socket is dropped from the registry rather
  than failing the HTTP request that triggered the event -- the write already
  succeeded, and a delivery problem is not the writer's problem.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Literal

from fastapi import WebSocket

logger = logging.getLogger(__name__)

# The set of events the frontend knows how to react to. Keeping these as a
# closed union means a typo in a router shows up as a type error, and the
# frontend's matching union in src/types/api.ts stays honest.
EventType = Literal[
    "board.created",
    "board.updated",
    "board.deleted",
    "board.activated",
    "column.created",
    "column.updated",
    "column.deleted",
    "column.reordered",
    "task.created",
    "task.updated",
    "task.deleted",
    "task.moved",
    "task.reordered",
]


@dataclass
class _Connection:
    """One live client socket and the board it cares about."""

    socket: WebSocket
    # None means "send me everything", an int narrows to a single board.
    board_id: int | None = None


@dataclass
class ConnectionManager:
    """Tracks connected clients and pushes events to the relevant ones."""

    _connections: list[_Connection] = field(default_factory=list)
    # Guards mutation of the list against concurrent connects/disconnects.
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def connect(self, socket: WebSocket, board_id: int | None = None) -> _Connection:
        """Accept a socket and register it for broadcasts."""
        await socket.accept()
        connection = _Connection(socket=socket, board_id=board_id)
        async with self._lock:
            self._connections.append(connection)
        logger.debug(
            "websocket connected (board_id=%s, total=%d)", board_id, len(self._connections)
        )
        return connection

    async def disconnect(self, connection: _Connection) -> None:
        """Remove a socket from the registry; safe to call more than once."""
        async with self._lock:
            if connection in self._connections:
                self._connections.remove(connection)
        logger.debug("websocket disconnected (total=%d)", len(self._connections))

    @property
    def connection_count(self) -> int:
        """Number of currently registered clients, surfaced by /api/health."""
        return len(self._connections)

    async def broadcast(
        self,
        event: EventType,
        payload: Any,
        *,
        board_id: int | None = None,
    ) -> None:
        """Send ``event`` to every interested client.

        A client receives the event when it subscribed to all boards, or when its
        board matches ``board_id``. Events with no ``board_id`` (board-level
        changes) go to everyone, since a board list needs refreshing regardless
        of which board is open.

        Failures are logged and the offending socket is dropped.
        """
        message = {"event": event, "board_id": board_id, "data": payload}

        # Snapshot under the lock, then send outside it: sending can block, and
        # holding the lock would serialise every client behind the slowest one.
        async with self._lock:
            targets = [
                c
                for c in self._connections
                if board_id is None or c.board_id is None or c.board_id == board_id
            ]

        if not targets:
            return

        results = await asyncio.gather(
            *(c.socket.send_json(message) for c in targets),
            return_exceptions=True,
        )

        stale = [c for c, result in zip(targets, results) if isinstance(result, Exception)]
        for connection in stale:
            logger.debug("dropping unreachable websocket during %s", event)
            await self.disconnect(connection)


# Process-wide singleton; imported by routers to publish events.
manager = ConnectionManager()
