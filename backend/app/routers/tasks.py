"""Task endpoints, including the move operation drag-and-drop depends on."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.crud import tasks as crud
from app.crud.tasks import TaskFilters
from app.database import get_db
from app.errors import ValidationError
from app.models import Priority, Task
from app.realtime import manager
from app.schemas.common import ApiResponse
from app.schemas.task import TaskCreate, TaskMove, TaskRead, TaskReorder, TaskUpdate

router = APIRouter(tags=["tasks"])


@router.get(
    "/tasks",
    response_model=ApiResponse[list[TaskRead]],
    summary="Search and filter tasks",
)
async def search_tasks(
    db: Session = Depends(get_db),
    board_id: Annotated[int | None, Query(description="Restrict to one board.")] = None,
    column_id: Annotated[int | None, Query(description="Restrict to one column.")] = None,
    q: Annotated[
        str | None,
        Query(description="Case-insensitive substring of title, description or tags."),
    ] = None,
    priority: Annotated[
        list[Priority] | None,
        Query(description="Repeatable, e.g. ?priority=high&priority=medium"),
    ] = None,
    tag: Annotated[
        list[str] | None,
        Query(description="Repeatable. Matches a task with any of these tags."),
    ] = None,
    completed: Annotated[
        bool | None, Query(description="Omit for both, true/false to narrow.")
    ] = None,
    overdue: Annotated[
        bool, Query(description="Only open tasks past their due date.")
    ] = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ApiResponse[list[TaskRead]]:
    """Return tasks matching the filters, highest priority and soonest due first.

    Backs the search screen. All parameters are optional and combine with AND,
    except repeated ``priority``/``tag`` values which combine with OR.
    """
    filters = TaskFilters(
        board_id=board_id,
        column_id=column_id,
        query=q,
        priorities=tuple(priority or ()),
        tags=tuple(tag or ()),
        is_completed=completed,
        overdue_only=overdue,
        limit=limit,
        offset=offset,
    )
    items = crud.search_tasks(db, filters)
    return ApiResponse.ok([TaskRead.model_validate(t) for t in items])


@router.get(
    "/boards/{board_id}/tags",
    response_model=ApiResponse[list[str]],
    summary="List every tag used on a board",
)
async def list_board_tags(board_id: int, db: Session = Depends(get_db)) -> ApiResponse[list[str]]:
    """Return the board's tag vocabulary, most frequently used first."""
    return ApiResponse.ok(crud.collect_tags(db, board_id))


@router.get(
    "/columns/{column_id}/tasks",
    response_model=ApiResponse[list[TaskRead]],
    summary="List a column's tasks",
)
async def list_column_tasks(
    column_id: int, db: Session = Depends(get_db)
) -> ApiResponse[list[TaskRead]]:
    """Return the column's tasks, top to bottom."""
    items = crud.list_tasks_in_column(db, column_id)
    return ApiResponse.ok([TaskRead.model_validate(t) for t in items])


@router.post(
    "/columns/{column_id}/tasks",
    response_model=ApiResponse[TaskRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create a task in a column",
)
async def create_task_in_column(
    column_id: int, payload: TaskCreate, db: Session = Depends(get_db)
) -> ApiResponse[TaskRead]:
    """Create a task in the given column. Any body ``column_id`` is ignored."""
    task = crud.create_task(db, column_id, payload)
    return ApiResponse.ok(await _created(task))


@router.post(
    "/tasks",
    response_model=ApiResponse[TaskRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create a task (column in body)",
)
async def create_task(payload: TaskCreate, db: Session = Depends(get_db)) -> ApiResponse[TaskRead]:
    """Create a task, taking the destination column from the request body."""
    if payload.column_id is None:
        raise ValidationError(
            "column_id is required when creating a task at this endpoint. "
            "Use POST /api/columns/{column_id}/tasks to take it from the path.",
            details={"field": "column_id"},
        )
    task = crud.create_task(db, payload.column_id, payload)
    return ApiResponse.ok(await _created(task))


@router.get(
    "/tasks/{task_id}",
    response_model=ApiResponse[TaskRead],
    summary="Get one task",
)
async def get_task(task_id: int, db: Session = Depends(get_db)) -> ApiResponse[TaskRead]:
    """Return a single task."""
    return ApiResponse.ok(TaskRead.model_validate(crud.get_task(db, task_id)))


@router.patch(
    "/tasks/{task_id}",
    response_model=ApiResponse[TaskRead],
    summary="Update a task's fields",
)
async def update_task(
    task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)
) -> ApiResponse[TaskRead]:
    """Update title, description, priority, due date or tags.

    Moving between columns is a separate operation -- see
    ``POST /api/tasks/{id}/move``.
    """
    task = crud.update_task(db, task_id, payload)
    result = TaskRead.model_validate(task)
    await manager.broadcast(
        "task.updated", result.model_dump(mode="json"), board_id=task.column.board_id
    )
    return ApiResponse.ok(result)


@router.post(
    "/tasks/{task_id}/move",
    response_model=ApiResponse[TaskRead],
    summary="Move a task to a column and position",
)
async def move_task(
    task_id: int, payload: TaskMove, db: Session = Depends(get_db)
) -> ApiResponse[TaskRead]:
    """Move a task between columns or within one, at a specific index.

    Called on drop by the drag-and-drop gesture. Out-of-range positions are
    clamped rather than rejected, so a fast drop never fails. Moving into a
    column flagged ``is_done_column`` marks the task complete.
    """
    task, from_column_id = crud.move_task(db, task_id, payload.column_id, payload.position)
    result = TaskRead.model_validate(task)

    # Include the origin column so a client can update both lanes without
    # re-fetching the whole board.
    await manager.broadcast(
        "task.moved",
        {
            "task": result.model_dump(mode="json"),
            "from_column_id": from_column_id,
            "to_column_id": payload.column_id,
        },
        board_id=task.column.board_id,
    )
    return ApiResponse.ok(result)


@router.put(
    "/columns/{column_id}/tasks/reorder",
    response_model=ApiResponse[list[TaskRead]],
    summary="Reorder tasks within a column",
)
async def reorder_tasks(
    column_id: int, payload: TaskReorder, db: Session = Depends(get_db)
) -> ApiResponse[list[TaskRead]]:
    """Set the exact top-to-bottom order of a column's tasks."""
    items = crud.reorder_tasks(db, column_id, payload.task_ids)
    result = [TaskRead.model_validate(t) for t in items]
    board_id = items[0].column.board_id if items else None
    await manager.broadcast(
        "task.reordered",
        {"column_id": column_id, "tasks": [t.model_dump(mode="json") for t in result]},
        board_id=board_id,
    )
    return ApiResponse.ok(result)


@router.delete(
    "/tasks/{task_id}",
    response_model=ApiResponse[dict[str, int]],
    summary="Delete a task",
)
async def delete_task(task_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict[str, int]]:
    """Delete a task and close the gap it leaves in its column."""
    board_id, column_id = crud.delete_task(db, task_id)
    await manager.broadcast(
        "task.deleted",
        {"id": task_id, "column_id": column_id},
        board_id=board_id,
    )
    return ApiResponse.ok({"id": task_id, "column_id": column_id})


async def _created(task: Task) -> TaskRead:
    """Serialise a freshly created task and announce it.

    Shared by the nested and flat create routes so both emit an identical event.
    """
    result = TaskRead.model_validate(task)
    await manager.broadcast(
        "task.created", result.model_dump(mode="json"), board_id=task.column.board_id
    )
    return result
