"""Task persistence: CRUD, cross-column moves, reordering and search."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from sqlalchemy import Select, String, case, cast, or_, select
from sqlalchemy.orm import Session

from app.crud.columns import get_column
from app.crud.ordering import apply_explicit_order, insert_at, resequence
from app.errors import NotFoundError, ValidationError
from app.models import Column, Priority, Task
from app.schemas.task import TaskCreate, TaskUpdate
from app.utils.time import to_naive_utc, utcnow

# Highest priority first when sorting search results. Needed because the values
# are stored as strings, where alphabetical order ("high", "low", "medium") is
# meaningless.
_PRIORITY_RANK = case(
    {Priority.HIGH.value: 0, Priority.MEDIUM.value: 1, Priority.LOW.value: 2},
    value=Task.priority,
    else_=3,
)


@dataclass(frozen=True)
class TaskFilters:
    """Filters accepted by :func:`search_tasks`.

    Grouped into an object rather than a long parameter list so the router can
    build it from query params in one place and so adding a filter does not
    change every call site.
    """

    board_id: int | None = None
    column_id: int | None = None
    query: str | None = None
    priorities: tuple[Priority, ...] = ()
    tags: tuple[str, ...] = ()
    # None means "either"; True/False narrow to done/open.
    is_completed: bool | None = None
    overdue_only: bool = False
    limit: int = 100
    offset: int = 0


def list_tasks_in_column(db: Session, column_id: int) -> list[Task]:
    """Return a column's tasks, top to bottom."""
    return list(
        db.scalars(
            select(Task).where(Task.column_id == column_id).order_by(Task.position, Task.id)
        )
    )


def get_task(db: Session, task_id: int) -> Task:
    """Return one task or raise :class:`NotFoundError`."""
    task = db.get(Task, task_id)
    if task is None:
        raise NotFoundError.for_entity("Task", task_id)
    return task


def create_task(db: Session, column_id: int, payload: TaskCreate) -> Task:
    """Create a task in ``column_id``, appending unless a position is given."""
    column = get_column(db, column_id)
    siblings = list_tasks_in_column(db, column_id)

    task = Task(
        column_id=column_id,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        due_date=to_naive_utc(payload.due_date),
        tags=list(payload.tags),
        position=len(siblings),
    )

    # A card created directly in a done column counts as done immediately.
    _sync_completion(task, column)

    db.add(task)

    if payload.position is not None:
        insert_at(siblings, task, payload.position)

    db.commit()
    db.refresh(task)
    return task


def update_task(db: Session, task_id: int, payload: TaskUpdate) -> Task:
    """Apply a partial update to a task's own fields.

    Deliberately cannot change ``column_id`` or ``position`` -- those go through
    :func:`move_task`, which is the only place that maintains sibling ordering.
    """
    task = get_task(db, task_id)

    changes = payload.model_dump(exclude_unset=True)
    if "due_date" in changes:
        changes["due_date"] = to_naive_utc(changes["due_date"])

    for field, value in changes.items():
        setattr(task, field, value)

    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, task_id: int) -> tuple[int, int]:
    """Delete a task; returns ``(board_id, column_id)`` for event broadcasting."""
    task = get_task(db, task_id)
    column_id = task.column_id
    board_id = task.column.board_id

    siblings = list_tasks_in_column(db, column_id)

    db.delete(task)
    db.flush()

    # Close the gap the deleted card left behind.
    resequence([t for t in siblings if t.id != task_id])
    db.commit()
    return board_id, column_id


def move_task(db: Session, task_id: int, column_id: int, position: int) -> tuple[Task, int]:
    """Move a task to ``column_id`` at ``position``.

    This is what a drag-and-drop drop gesture calls. Returns the task plus the
    column it came from, so the caller can tell clients which two lanes changed.

    Both lanes are resequenced, and completion state is re-derived from the
    destination column -- dragging a card into Done marks it complete, dragging it
    back out reopens it.
    """
    task = get_task(db, task_id)
    target = get_column(db, column_id)
    source_column_id = task.column_id

    if source_column_id != column_id:
        source = get_column(db, source_column_id)
        # Moving across boards would silently relocate a card out of the board the
        # user is looking at, so it is rejected rather than guessed at.
        if source.board_id != target.board_id:
            raise ValidationError(
                "Cannot move a task to a column on a different board.",
                details={
                    "task_id": task_id,
                    "from_board_id": source.board_id,
                    "to_board_id": target.board_id,
                },
            )

    if source_column_id == column_id:
        # Reorder in place. The session has autoflush disabled, so this query
        # reflects committed state and includes the task itself.
        siblings = list_tasks_in_column(db, column_id)
        insert_at(siblings, task, position)
    else:
        old_siblings = [t for t in list_tasks_in_column(db, source_column_id) if t.id != task_id]
        resequence(old_siblings)

        task.column_id = column_id
        # Fetched after the reassignment but before any flush, so the result does
        # not yet contain this task -- insert_at then places it exactly once.
        new_siblings = list_tasks_in_column(db, column_id)
        insert_at(new_siblings, task, position)

        _sync_completion(task, target)

    db.commit()
    db.refresh(task)
    return task, source_column_id


def reorder_tasks(db: Session, column_id: int, task_ids: list[int]) -> list[Task]:
    """Set the exact top-to-bottom order of one column's tasks."""
    get_column(db, column_id)
    tasks = list_tasks_in_column(db, column_id)
    reordered = apply_explicit_order(tasks, task_ids)
    db.commit()
    return reordered


def search_tasks(db: Session, filters: TaskFilters) -> list[Task]:
    """Return tasks matching ``filters``, most important first.

    Tag filtering happens in Python because tags are a JSON array (see
    :class:`app.models.task.Task`); everything else is pushed into SQL. At
    personal-board scale the difference is unmeasurable, but it does mean the
    ``limit`` is applied after tag filtering to avoid returning a short page.
    """
    statement: Select[tuple[Task]] = select(Task)

    # Only join when the filter needs board scope -- an unnecessary join would
    # change nothing but cost a lookup.
    if filters.board_id is not None:
        statement = statement.join(Column, Task.column_id == Column.id).where(
            Column.board_id == filters.board_id
        )

    if filters.column_id is not None:
        statement = statement.where(Task.column_id == filters.column_id)

    if filters.query:
        # Case-insensitive substring across title, description and tags. Tags are
        # a JSON array, so this matches against its serialised text -- crude, but
        # a search box wants recall, and it keeps the whole query in one pass.
        # A NULL description yields NULL here, which OR correctly ignores.
        pattern = f"%{filters.query.strip().lower()}%"
        statement = statement.where(
            or_(
                Task.title.ilike(pattern),
                Task.description.ilike(pattern),
                cast(Task.tags, String).ilike(pattern),
            )
        )

    if filters.priorities:
        statement = statement.where(Task.priority.in_(filters.priorities))

    if filters.is_completed is not None:
        statement = statement.where(Task.is_completed.is_(filters.is_completed))

    if filters.overdue_only:
        statement = statement.where(
            Task.due_date.is_not(None),
            Task.due_date < utcnow(),
            Task.is_completed.is_(False),
        )

    statement = statement.order_by(
        _PRIORITY_RANK,
        # NULL due dates sort last: something with a deadline outranks something
        # without one at the same priority.
        Task.due_date.is_(None),
        Task.due_date,
        Task.position,
        Task.id,
    )

    results = list(db.scalars(statement))

    if filters.tags:
        wanted = {tag.lower() for tag in filters.tags}
        results = [task for task in results if wanted & {t.lower() for t in task.tags}]

    return results[filters.offset : filters.offset + filters.limit]


def collect_tags(db: Session, board_id: int) -> list[str]:
    """Return every distinct tag used on a board, most frequent first.

    Powers the tag filter chips, which need the real vocabulary of the board
    rather than a hardcoded list.
    """
    tasks = db.scalars(
        select(Task).join(Column, Task.column_id == Column.id).where(Column.board_id == board_id)
    )
    counter: Counter[str] = Counter()
    for task in tasks:
        counter.update(tag.lower() for tag in task.tags)
    return [tag for tag, _ in counter.most_common()]


def _sync_completion(task: Task, column: Column) -> None:
    """Derive a task's completion state from the column it now sits in.

    ``completed_at`` is preserved when a task moves between two done columns, so
    the original completion time survives a workflow with several terminal lanes.
    """
    if column.is_done_column:
        if not task.is_completed:
            task.is_completed = True
            task.completed_at = utcnow()
    else:
        task.is_completed = False
        task.completed_at = None
