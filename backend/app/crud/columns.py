"""Column persistence and ordering."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud.boards import get_board
from app.crud.ordering import apply_explicit_order, insert_at, resequence
from app.errors import ConflictError, NotFoundError
from app.models import Column
from app.schemas.column import ColumnCreate, ColumnUpdate
from app.utils.time import utcnow


def list_columns(db: Session, board_id: int) -> list[Column]:
    """Return a board's columns, left to right."""
    get_board(db, board_id)  # 404 for an unknown board rather than an empty list
    return list(
        db.scalars(
            select(Column).where(Column.board_id == board_id).order_by(Column.position, Column.id)
        )
    )


def get_column(db: Session, column_id: int) -> Column:
    """Return one column or raise :class:`NotFoundError`."""
    column = db.get(Column, column_id)
    if column is None:
        raise NotFoundError.for_entity("Column", column_id)
    return column


def create_column(db: Session, board_id: int, payload: ColumnCreate) -> Column:
    """Add a column to a board, appending unless a position is given."""
    get_board(db, board_id)
    columns = list_columns(db, board_id)

    column = Column(
        board_id=board_id,
        name=payload.name,
        is_done_column=payload.is_done_column,
        position=len(columns),
    )
    db.add(column)

    if payload.position is not None:
        insert_at(columns, column, payload.position)

    db.commit()
    db.refresh(column)
    return column


def update_column(db: Session, column_id: int, payload: ColumnUpdate) -> Column:
    """Apply a partial update to a column.

    Toggling ``is_done_column`` retroactively fixes the completion state of the
    tasks already sitting in it. Without this, flagging an existing "Done" column
    would leave its cards permanently uncounted by the stats screen.
    """
    column = get_column(db, column_id)
    changes = payload.model_dump(exclude_unset=True)

    done_flag_changed = (
        "is_done_column" in changes and changes["is_done_column"] != column.is_done_column
    )

    for field, value in changes.items():
        setattr(column, field, value)

    if done_flag_changed:
        now = utcnow()
        for task in column.tasks:
            task.is_completed = column.is_done_column
            task.completed_at = now if column.is_done_column else None

    db.commit()
    db.refresh(column)
    return column


def delete_column(db: Session, column_id: int) -> int:
    """Delete a column and its tasks; returns the owning board id.

    Refuses to delete a board's last column, mirroring the last-board rule: a
    board with no lanes cannot be rendered or added to.
    """
    column = get_column(db, column_id)
    board_id = column.board_id

    siblings = list_columns(db, board_id)
    if len(siblings) <= 1:
        raise ConflictError(
            "Cannot delete the last column on a board.",
            code="last_column",
        )

    db.delete(column)
    db.flush()

    resequence([c for c in siblings if c.id != column_id])
    db.commit()
    return board_id


def reorder_columns(db: Session, board_id: int, column_ids: list[int]) -> list[Column]:
    """Set the left-to-right order of a board's columns."""
    columns = list_columns(db, board_id)
    reordered = apply_explicit_order(columns, column_ids)
    db.commit()
    return reordered
