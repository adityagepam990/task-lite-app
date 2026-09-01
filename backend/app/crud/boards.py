"""Board persistence, including the single-active-board invariant."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud.ordering import apply_explicit_order, resequence
from app.errors import ConflictError, NotFoundError
from app.models import Board, Column
from app.schemas.board import BoardCreate, BoardUpdate

# The lanes a new board gets when the client asks for defaults. The last one is
# flagged as the done column, which is what makes completion stats work out of
# the box instead of requiring the user to configure anything.
DEFAULT_COLUMNS: tuple[tuple[str, bool], ...] = (
    ("Backlog", False),
    ("To Do", False),
    ("In Progress", False),
    ("Done", True),
)


def list_boards(db: Session) -> list[Board]:
    """Return every board ordered for the switcher."""
    return list(db.scalars(select(Board).order_by(Board.position, Board.id)))


def get_board(db: Session, board_id: int) -> Board:
    """Return one board or raise :class:`NotFoundError`."""
    board = db.get(Board, board_id)
    if board is None:
        raise NotFoundError.for_entity("Board", board_id)
    return board


def get_active_board(db: Session) -> Board:
    """Return the active board.

    Falls back to the first board and promotes it when no board is flagged --
    which can happen if the active board was just deleted. Callers get a usable
    board rather than having to handle a "no active board" state everywhere.
    """
    board = db.scalars(select(Board).where(Board.is_active.is_(True))).first()
    if board is not None:
        return board

    fallback = db.scalars(select(Board).order_by(Board.position, Board.id)).first()
    if fallback is None:
        raise NotFoundError(
            "No boards exist yet. Create one first.",
            code="no_boards",
            status_code=404,
        )

    fallback.is_active = True
    db.commit()
    db.refresh(fallback)
    return fallback


def create_board(db: Session, payload: BoardCreate) -> Board:
    """Create a board, optionally with default columns, optionally activated."""
    count = len(list_boards(db))

    board = Board(
        name=payload.name,
        description=payload.description,
        color=payload.color,
        position=count,
        # First board ever created is active by definition -- otherwise the app
        # would open to nothing.
        is_active=payload.make_active or count == 0,
    )

    if payload.with_default_columns:
        board.columns = [
            Column(name=name, position=index, is_done_column=is_done)
            for index, (name, is_done) in enumerate(DEFAULT_COLUMNS)
        ]

    db.add(board)

    if board.is_active:
        db.flush()  # assign board.id before comparing against it
        _deactivate_others(db, board.id)

    db.commit()
    db.refresh(board)
    return board


def update_board(db: Session, board_id: int, payload: BoardUpdate) -> Board:
    """Apply a partial update to a board."""
    board = get_board(db, board_id)

    # exclude_unset distinguishes "not mentioned" from "explicitly set to null",
    # so PATCH {"description": null} clears the description while PATCH {} does
    # not touch it.
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(board, field, value)

    db.commit()
    db.refresh(board)
    return board


def activate_board(db: Session, board_id: int) -> Board:
    """Make ``board_id`` the one active board."""
    board = get_board(db, board_id)
    board.is_active = True
    _deactivate_others(db, board.id)
    db.commit()
    db.refresh(board)
    return board


def delete_board(db: Session, board_id: int) -> None:
    """Delete a board and everything on it.

    Refuses to delete the last remaining board: the app has no empty state for
    "no boards at all", and silently recreating one would be surprising.
    """
    board = get_board(db, board_id)

    boards = list_boards(db)
    if len(boards) <= 1:
        raise ConflictError(
            "Cannot delete your only board. Create another board first.",
            code="last_board",
        )

    was_active = board.is_active
    db.delete(board)
    db.flush()

    remaining = [b for b in list_boards(db) if b.id != board_id]
    resequence(remaining)

    # Promote a neighbour so the app always has somewhere to land.
    if was_active and remaining:
        remaining[0].is_active = True

    db.commit()


def reorder_boards(db: Session, board_ids: list[int]) -> list[Board]:
    """Set the order boards appear in the switcher."""
    boards = list_boards(db)
    reordered = apply_explicit_order(boards, board_ids)
    db.commit()
    return reordered


def _deactivate_others(db: Session, keep_id: int) -> None:
    """Clear ``is_active`` on every board except ``keep_id``.

    A bulk UPDATE rather than a loop so activating a board is one statement
    regardless of how many boards exist.
    """
    db.query(Board).filter(Board.id != keep_id, Board.is_active.is_(True)).update(
        {Board.is_active: False}, synchronize_session="fetch"
    )
