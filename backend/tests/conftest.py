"""Shared pytest fixtures.

Two layers of isolation, because the app touches a database in two different
places:

1. ``app.main``'s lifespan hook calls ``create_all()`` / seeds using the
   module-level engine from :mod:`app.database` -- built once at import time
   from ``config.toml``. Environment variables must be set *before* that first
   import, which is why they are set here at module load, before ``app.main``
   (or anything importing it) is ever imported by a test.
2. Individual requests use :func:`app.database.get_db` as a FastAPI dependency,
   which the ``client`` fixture overrides to point at a fresh per-test session.

Without (1), every test run would create/seed the developer's real
``tasklite.db`` on disk; with only (1) and not (2), all tests would share one
process-wide in-memory database and leak state between each other.
"""

from __future__ import annotations

import os
from collections.abc import Generator

# Must happen before any `app.*` module is imported anywhere in the test run.
os.environ["TASKLITE_DATABASE__PATH"] = ":memory:"
os.environ["TASKLITE_SEED__ENABLED"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    """A fresh in-memory database, schema created, per test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """An HTTP client wired to the in-memory per-test database."""

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
