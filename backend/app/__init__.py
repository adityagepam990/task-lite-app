"""TaskLite -- a local-first personal Kanban backend.

The package is laid out by responsibility:

* :mod:`app.config`    -- file-based settings (config.toml + env overrides)
* :mod:`app.database`  -- SQLAlchemy engine, session factory, declarative base
* :mod:`app.models`    -- ORM models (Board, Column, Task)
* :mod:`app.schemas`   -- Pydantic request/response models
* :mod:`app.crud`      -- persistence logic, including all position bookkeeping
* :mod:`app.routers`   -- HTTP + WebSocket endpoints
* :mod:`app.errors`    -- typed application errors and their HTTP translation
* :mod:`app.realtime`  -- WebSocket connection registry and event broadcasting
"""

__all__ = ["__version__"]

__version__ = "1.0.0"
