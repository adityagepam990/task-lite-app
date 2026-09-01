"""Starter-content seeding."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Board
from app.seed import seed_if_empty


def test_seed_populates_empty_database(db_session: Session) -> None:
    seeded = seed_if_empty(db_session)
    assert seeded is True

    boards = list(db_session.scalars(select(Board)))
    assert {b.name for b in boards} == {"Personal", "Work", "Side Projects"}
    assert sum(b.is_active for b in boards) == 1

    for board in boards:
        assert len(board.columns) == 4
        assert any(c.is_done_column for c in board.columns)


def test_seed_does_nothing_when_data_exists(db_session: Session) -> None:
    db_session.add(Board(name="Existing", position=0, is_active=True))
    db_session.commit()

    seeded = seed_if_empty(db_session)
    assert seeded is False

    boards = list(db_session.scalars(select(Board)))
    assert [b.name for b in boards] == ["Existing"]
