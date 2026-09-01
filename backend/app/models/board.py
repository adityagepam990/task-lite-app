"""The Board model -- a single Kanban board such as "Personal" or "Work"."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:  # pragma: no cover - import cycle only exists for type checkers
    from app.models.column import Column


class Board(Base):
    """A board owns an ordered set of columns, which in turn own tasks.

    Exactly one board is "active" at a time -- the one the app opens on. That
    invariant is enforced in :mod:`app.crud.boards` rather than by a database
    constraint, because SQLite cannot express a partial unique index over a
    boolean as cleanly as the application can just clear the previous winner.
    """

    __tablename__ = "boards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Accent colour (hex, e.g. "#6366F1") the UI uses to tint the board's header
    # and its entry in the board switcher.
    color: Mapped[str] = mapped_column(String(9), nullable=False, default="#6366F1")

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Display order in the board switcher. Contiguous from 0; see crud.reindex.
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Ordered eagerly by position so callers never have to sort. delete-orphan
    # plus the SQLite foreign_keys pragma means deleting a board removes its
    # columns and (transitively) their tasks.
    columns: Mapped[list["Column"]] = relationship(
        back_populates="board",
        cascade="all, delete-orphan",
        order_by="Column.position",
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Board id={self.id} name={self.name!r} active={self.is_active}>"
