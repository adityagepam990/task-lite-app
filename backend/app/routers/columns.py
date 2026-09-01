"""Column endpoints.

Columns are addressed two ways: nested under a board when creating or listing
(the board is the natural parent), and flat by id when updating or deleting (the
client already knows the id and the parent adds nothing). Hence no router-level
prefix -- each route spells out its own path.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.crud import columns as crud
from app.database import get_db
from app.realtime import manager
from app.schemas.column import (
    ColumnCreate,
    ColumnRead,
    ColumnReorder,
    ColumnUpdate,
    ColumnWithTasks,
)
from app.schemas.common import ApiResponse

router = APIRouter(tags=["columns"])


@router.get(
    "/boards/{board_id}/columns",
    response_model=ApiResponse[list[ColumnWithTasks]],
    summary="List a board's columns with their tasks",
)
async def list_columns(
    board_id: int, db: Session = Depends(get_db)
) -> ApiResponse[list[ColumnWithTasks]]:
    """Return the board's columns left to right, each with its ordered tasks."""
    items = crud.list_columns(db, board_id)
    return ApiResponse.ok([ColumnWithTasks.model_validate(c) for c in items])


@router.post(
    "/boards/{board_id}/columns",
    response_model=ApiResponse[ColumnWithTasks],
    status_code=status.HTTP_201_CREATED,
    summary="Add a column to a board",
)
async def create_column(
    board_id: int, payload: ColumnCreate, db: Session = Depends(get_db)
) -> ApiResponse[ColumnWithTasks]:
    """Create a column, appended to the right unless a position is supplied."""
    column = crud.create_column(db, board_id, payload)
    result = ColumnWithTasks.model_validate(column)
    await manager.broadcast("column.created", result.model_dump(mode="json"), board_id=board_id)
    return ApiResponse.ok(result)


@router.put(
    "/boards/{board_id}/columns/reorder",
    response_model=ApiResponse[list[ColumnRead]],
    summary="Reorder a board's columns",
)
async def reorder_columns(
    board_id: int, payload: ColumnReorder, db: Session = Depends(get_db)
) -> ApiResponse[list[ColumnRead]]:
    """Set the left-to-right order of the board's columns."""
    items = crud.reorder_columns(db, board_id, payload.column_ids)
    result = [ColumnRead.model_validate(c) for c in items]
    await manager.broadcast(
        "column.reordered",
        [c.model_dump(mode="json") for c in result],
        board_id=board_id,
    )
    return ApiResponse.ok(result)


@router.get(
    "/columns/{column_id}",
    response_model=ApiResponse[ColumnWithTasks],
    summary="Get one column with its tasks",
)
async def get_column(
    column_id: int, db: Session = Depends(get_db)
) -> ApiResponse[ColumnWithTasks]:
    """Return a single column including its ordered tasks."""
    column = crud.get_column(db, column_id)
    return ApiResponse.ok(ColumnWithTasks.model_validate(column))


@router.patch(
    "/columns/{column_id}",
    response_model=ApiResponse[ColumnWithTasks],
    summary="Update a column",
)
async def update_column(
    column_id: int, payload: ColumnUpdate, db: Session = Depends(get_db)
) -> ApiResponse[ColumnWithTasks]:
    """Rename a column or toggle whether it marks tasks complete.

    Toggling the done flag restamps the tasks already in the column, so the
    response includes them.
    """
    column = crud.update_column(db, column_id, payload)
    result = ColumnWithTasks.model_validate(column)
    await manager.broadcast(
        "column.updated", result.model_dump(mode="json"), board_id=column.board_id
    )
    return ApiResponse.ok(result)


@router.delete(
    "/columns/{column_id}",
    response_model=ApiResponse[dict[str, int]],
    summary="Delete a column and its tasks",
)
async def delete_column(
    column_id: int, db: Session = Depends(get_db)
) -> ApiResponse[dict[str, int]]:
    """Delete a column and everything in it. Refuses on a board's last column."""
    board_id = crud.delete_column(db, column_id)
    await manager.broadcast(
        "column.deleted", {"id": column_id, "board_id": board_id}, board_id=board_id
    )
    return ApiResponse.ok({"id": column_id, "board_id": board_id})
