"""Aggregations for the statistics screen."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud.boards import get_board
from app.models import Column, Priority, Task
from app.schemas.stats import BoardStats, ColumnCount, DailyCount, PriorityBreakdown
from app.utils.time import start_of_day, start_of_week, utcnow

# A task due within this window is "due soon" -- long enough to be a useful
# heads-up, short enough that the count stays small and actionable.
DUE_SOON_DAYS = 3
TREND_DAYS = 7
TOP_TAG_COUNT = 5


def board_stats(db: Session, board_id: int) -> BoardStats:
    """Compute every figure the stats screen shows, in one pass over the board.

    Loading the board's tasks once and aggregating in Python beats issuing a
    dozen COUNT queries here: the row count is small (a personal board), and it
    keeps all the definitions -- what counts as overdue, what "this week" means --
    visible together instead of scattered across separate SQL statements.
    """
    board = get_board(db, board_id)

    columns = list(
        db.scalars(
            select(Column).where(Column.board_id == board_id).order_by(Column.position, Column.id)
        )
    )
    column_ids = [c.id for c in columns]

    tasks: list[Task] = []
    if column_ids:
        tasks = list(db.scalars(select(Task).where(Task.column_id.in_(column_ids))))

    now = utcnow()
    week_start = start_of_week(now)
    due_soon_cutoff = now + timedelta(days=DUE_SOON_DAYS)

    open_tasks = [t for t in tasks if not t.is_completed]
    completed_tasks = [t for t in tasks if t.is_completed]

    priority_counts = Counter(t.priority for t in open_tasks)
    by_priority = PriorityBreakdown(
        low=priority_counts.get(Priority.LOW, 0),
        medium=priority_counts.get(Priority.MEDIUM, 0),
        high=priority_counts.get(Priority.HIGH, 0),
    )

    tasks_by_column: Counter[int] = Counter(t.column_id for t in tasks)
    by_column = [
        ColumnCount(
            column_id=column.id,
            column_name=column.name,
            count=tasks_by_column.get(column.id, 0),
        )
        for column in columns
    ]

    tag_counts: Counter[str] = Counter()
    for task in open_tasks:
        tag_counts.update(tag.lower() for tag in task.tags)

    return BoardStats(
        board_id=board.id,
        board_name=board.name,
        total_tasks=len(tasks),
        open_tasks=len(open_tasks),
        completed_tasks=len(completed_tasks),
        completed_this_week=sum(
            1 for t in completed_tasks if t.completed_at is not None and t.completed_at >= week_start
        ),
        created_this_week=sum(1 for t in tasks if t.created_at >= week_start),
        overdue_tasks=sum(1 for t in open_tasks if t.due_date is not None and t.due_date < now),
        due_soon_tasks=sum(
            1
            for t in open_tasks
            if t.due_date is not None and now <= t.due_date <= due_soon_cutoff
        ),
        by_priority=by_priority,
        by_column=by_column,
        completion_trend=_completion_trend(completed_tasks, now),
        top_tags=[tag for tag, _ in tag_counts.most_common(TOP_TAG_COUNT)],
    )


def _completion_trend(completed: list[Task], now: datetime) -> list[DailyCount]:
    """Build a fixed-length per-day completion series, oldest first.

    Every day in the window is present even when nothing was completed, so the
    frontend can render a sparkline without having to fill gaps itself.
    """
    today = start_of_day(now)

    buckets: Counter[str] = Counter()
    for task in completed:
        if task.completed_at is not None:
            buckets[task.completed_at.date().isoformat()] += 1

    series: list[DailyCount] = []
    for offset in range(TREND_DAYS - 1, -1, -1):
        day = (today - timedelta(days=offset)).date().isoformat()
        series.append(DailyCount(date=day, count=buckets.get(day, 0)))
    return series
