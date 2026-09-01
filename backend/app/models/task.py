"""The Task model -- a single card on the board."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import Priority

if TYPE_CHECKING:  # pragma: no cover
    from app.models.column import Column


class Task(Base):
    """A card, belonging to exactly one column.

    Tags are stored as a JSON array rather than in a join table. For a
    single-user app that only ever filters tags client-side this avoids two
    extra tables and a many-to-many relationship; the tradeoff is that you
    cannot efficiently query "all tasks with tag X" in SQL. If tag-based
    server-side filtering ever matters, promote this to a proper Tag table.
    """

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    column_id: Mapped[int] = mapped_column(
        ForeignKey("columns.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # native_enum=False stores a VARCHAR with a CHECK constraint instead of a
    # database enum type. SQLite has no enum type, and this keeps the stored
    # value human-readable when inspecting the file with any SQLite browser.
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority, native_enum=False, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=Priority.MEDIUM,
    )

    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # list[str]; defaults to an empty list rather than NULL so clients never have
    # to null-check before mapping over it.
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    # Vertical order within the column. Contiguous from 0.
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Derived from the column's is_done_column flag whenever a task moves, but
    # stored so that statistics queries stay simple and so the completion
    # timestamp survives a column being renamed or re-flagged.
    is_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    column: Mapped["Column"] = relationship(back_populates="tasks")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Task id={self.id} title={self.title!r} column_id={self.column_id}>"
