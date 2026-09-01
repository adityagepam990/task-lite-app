"""SQLAlchemy engine, session management and declarative base.

Persistence is a single SQLite file. Two SQLite-specific details matter here and
are easy to get wrong:

* ``check_same_thread=False`` -- FastAPI serves requests from a thread pool, so a
  connection created on one thread may be used on another. Safe because each
  request gets its own :class:`Session`.
* ``PRAGMA foreign_keys=ON`` -- SQLite ignores foreign keys unless you ask for
  them *per connection*. Without this, deleting a board would orphan its columns
  and tasks instead of cascading.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model."""


def _engine_kwargs(url: str, echo: bool) -> dict[str, Any]:
    """Build engine kwargs, special-casing in-memory SQLite.

    An in-memory database lives inside a single connection, so the default pool
    (which opens connections on demand) would hand out empty databases. StaticPool
    reuses one connection and keeps the schema alive for the process lifetime --
    exactly what the test suite needs.
    """
    kwargs: dict[str, Any] = {
        "echo": echo,
        "connect_args": {"check_same_thread": False},
    }
    if url == "sqlite://":
        kwargs["poolclass"] = StaticPool
    return kwargs


_settings = get_settings()

engine: Engine = create_engine(
    _settings.database.url,
    **_engine_kwargs(_settings.database.url, _settings.database.echo_sql),
)

# expire_on_commit=False lets a route return an ORM object after commit without
# triggering a fresh SELECT for every attribute (and without risking a
# DetachedInstanceError once the session closes).
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:
    """Turn on foreign key enforcement for each new SQLite connection."""
    # Guard on the presence of the SQLite cursor API so this listener is a no-op
    # if the engine is ever pointed at another database.
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    except Exception:  # pragma: no cover - non-SQLite backends
        pass
    finally:
        cursor.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a request-scoped session.

    The session is always closed. Commits are the caller's responsibility so a
    route can group several writes into one transaction; on an unhandled
    exception the transaction is rolled back before closing.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_all() -> None:
    """Create any missing tables.

    Fine for a single-user local app. A multi-developer or deployed project would
    reach for Alembic migrations instead of create-if-missing.
    """
    # Importing for side effects: model modules must be loaded before create_all
    # so their tables are registered on Base.metadata.
    from app import models  # noqa: F401  (registers mappers)

    Base.metadata.create_all(bind=engine)
