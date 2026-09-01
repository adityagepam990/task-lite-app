"""HTTP and WebSocket routers.

Each module owns one resource and is mounted under ``/api`` by
:mod:`app.main`. Routers deliberately contain no ordering or invariant logic --
that all lives in :mod:`app.crud`.
"""

from app.routers import boards, columns, stats, tasks, ws

__all__ = ["boards", "columns", "stats", "tasks", "ws"]
