"""Statistics endpoints backing the app's stats screen."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.crud import boards as boards_crud
from app.crud import stats as crud
from app.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.stats import BoardStats

router = APIRouter(tags=["stats"])


@router.get(
    "/stats",
    response_model=ApiResponse[BoardStats],
    summary="Statistics for the active board",
)
async def active_board_stats(db: Session = Depends(get_db)) -> ApiResponse[BoardStats]:
    """Return statistics for whichever board is currently active.

    The stats tab follows the active board, so it can call this without first
    having to know which board that is.
    """
    board = boards_crud.get_active_board(db)
    return ApiResponse.ok(crud.board_stats(db, board.id))


@router.get(
    "/boards/{board_id}/stats",
    response_model=ApiResponse[BoardStats],
    summary="Statistics for one board",
)
async def board_stats(board_id: int, db: Session = Depends(get_db)) -> ApiResponse[BoardStats]:
    """Return counts, breakdowns and a 7-day completion trend for one board."""
    return ApiResponse.ok(crud.board_stats(db, board_id))
