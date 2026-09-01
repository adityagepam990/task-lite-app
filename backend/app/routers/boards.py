"""Board endpoints.

Note the route ordering: ``/boards/active`` is declared before ``/boards/{id}``.
FastAPI matches in declaration order, so the reverse would make "active" get
parsed as an integer path parameter and always 422.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.crud import boards as crud
from app.database import get_db
from app.realtime import manager
from app.schemas.board import (
    BoardCreate,
    BoardRead,
    BoardReorder,
    BoardUpdate,
    BoardWithColumns,
)
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/boards", tags=["boards"])


@router.get(
    "",
    response_model=ApiResponse[list[BoardRead]],
    summary="List all boards",
)
async def list_boards(db: Session = Depends(get_db)) -> ApiResponse[list[BoardRead]]:
    """Return every board, ordered for the switcher. Columns are omitted."""
    items = crud.list_boards(db)
    return ApiResponse.ok([BoardRead.model_validate(b) for b in items])


@router.get(
    "/active",
    response_model=ApiResponse[BoardWithColumns],
    summary="Get the active board with its full column/task tree",
)
async def get_active_board(db: Session = Depends(get_db)) -> ApiResponse[BoardWithColumns]:
    """Return the board the app should open on, including all columns and tasks.

    This is the single request the app makes on launch and on pull-to-refresh.
    """
    board = crud.get_active_board(db)
    return ApiResponse.ok(BoardWithColumns.model_validate(board))


@router.get(
    "/{board_id}",
    response_model=ApiResponse[BoardWithColumns],
    summary="Get one board with its full column/task tree",
)
async def get_board(
    board_id: int, db: Session = Depends(get_db)
) -> ApiResponse[BoardWithColumns]:
    """Return a board including every column and task on it."""
    board = crud.get_board(db, board_id)
    return ApiResponse.ok(BoardWithColumns.model_validate(board))


@router.post(
    "",
    response_model=ApiResponse[BoardWithColumns],
    status_code=status.HTTP_201_CREATED,
    summary="Create a board",
)
async def create_board(
    payload: BoardCreate, db: Session = Depends(get_db)
) -> ApiResponse[BoardWithColumns]:
    """Create a board, by default with the four standard columns."""
    board = crud.create_board(db, payload)
    result = BoardWithColumns.model_validate(board)
    await manager.broadcast("board.created", result.model_dump(mode="json"))
    return ApiResponse.ok(result)


@router.patch(
    "/{board_id}",
    response_model=ApiResponse[BoardRead],
    summary="Update a board",
)
async def update_board(
    board_id: int, payload: BoardUpdate, db: Session = Depends(get_db)
) -> ApiResponse[BoardRead]:
    """Rename a board or change its description/accent colour."""
    board = crud.update_board(db, board_id, payload)
    result = BoardRead.model_validate(board)
    await manager.broadcast("board.updated", result.model_dump(mode="json"), board_id=board_id)
    return ApiResponse.ok(result)


@router.post(
    "/{board_id}/activate",
    response_model=ApiResponse[BoardWithColumns],
    summary="Switch to a board",
)
async def activate_board(
    board_id: int, db: Session = Depends(get_db)
) -> ApiResponse[BoardWithColumns]:
    """Make this the active board and return it fully populated.

    Returns the whole tree so the client can switch boards with one round trip
    instead of activating and then fetching.
    """
    board = crud.activate_board(db, board_id)
    result = BoardWithColumns.model_validate(board)
    await manager.broadcast("board.activated", result.model_dump(mode="json"))
    return ApiResponse.ok(result)


@router.put(
    "/reorder",
    response_model=ApiResponse[list[BoardRead]],
    summary="Reorder the board list",
)
async def reorder_boards(
    payload: BoardReorder, db: Session = Depends(get_db)
) -> ApiResponse[list[BoardRead]]:
    """Set the order boards appear in the switcher."""
    items = crud.reorder_boards(db, payload.board_ids)
    result = [BoardRead.model_validate(b) for b in items]
    await manager.broadcast("board.updated", [b.model_dump(mode="json") for b in result])
    return ApiResponse.ok(result)


@router.delete(
    "/{board_id}",
    response_model=ApiResponse[dict[str, int]],
    summary="Delete a board and everything on it",
)
async def delete_board(board_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict[str, int]]:
    """Delete a board, its columns and its tasks. Refuses on the last board."""
    crud.delete_board(db, board_id)
    await manager.broadcast("board.deleted", {"id": board_id})
    return ApiResponse.ok({"id": board_id})
