"""The Column model -- an ordered lane within a board ("To Do", "Done", ...)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:  # pragma: no cover
    from app.models.board import Board
    from app.models.task import Task


class Column(Base):
    """A vertical lane holding an ordered list of tasks.

    ``is_done_column`` is what gives the statistics screen something to count. A
    task moved into a done column is stamped as completed; moved back out, the
    stamp is cleared. That keeps "completed this week" meaningful without asking
    the user to tick a separate checkbox.
    """

    __tablename__ = "columns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # ondelete="CASCADE" handles deletes issued as raw SQL; the ORM-level
    # cascade on Board.columns handles deletes that go through a session.
    board_id: Mapped[int] = mapped_column(
        ForeignKey("boards.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)

    # Left-to-right order within the board. Contiguous from 0.
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    is_done_column: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    board: Mapped["Board"] = relationship(back_populates="columns")

    tasks: Mapped[list["Task"]] = relationship(
        back_populates="column",
        cascade="all, delete-orphan",
        order_by="Task.position",
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Column id={self.id} name={self.name!r} position={self.position}>"
