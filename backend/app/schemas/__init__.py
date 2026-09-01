"""Pydantic request and response models.

Naming convention, applied consistently across the three entities:

* ``XCreate`` -- accepted on POST; required fields are genuinely required
* ``XUpdate`` -- accepted on PATCH; every field optional, absent means "leave it"
* ``XRead``   -- returned to the client

Read models never contain the ORM object itself, so a schema change cannot
accidentally leak a new database column to clients.
"""

from app.schemas.board import BoardCreate, BoardRead, BoardReorder, BoardUpdate, BoardWithColumns
from app.schemas.column import (
    ColumnCreate,
    ColumnRead,
    ColumnReorder,
    ColumnUpdate,
    ColumnWithTasks,
)
from app.schemas.common import ApiResponse, ErrorBody, ErrorResponse, UtcDatetime
from app.schemas.stats import BoardStats, ColumnCount, DailyCount, PriorityBreakdown
from app.schemas.task import TaskCreate, TaskMove, TaskRead, TaskReorder, TaskUpdate

__all__ = [
    "ApiResponse",
    "BoardCreate",
    "BoardRead",
    "BoardReorder",
    "BoardStats",
    "BoardUpdate",
    "BoardWithColumns",
    "ColumnCount",
    "ColumnCreate",
    "ColumnRead",
    "ColumnReorder",
    "ColumnUpdate",
    "ColumnWithTasks",
    "DailyCount",
    "ErrorBody",
    "ErrorResponse",
    "PriorityBreakdown",
    "TaskCreate",
    "TaskMove",
    "TaskRead",
    "TaskReorder",
    "TaskUpdate",
    "UtcDatetime",
]
