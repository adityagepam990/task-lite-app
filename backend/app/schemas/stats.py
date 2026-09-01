"""Statistics schemas backing the app's stats screen."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PriorityBreakdown(BaseModel):
    """Counts of open tasks per priority level."""

    low: int = 0
    medium: int = 0
    high: int = 0

    @property
    def total(self) -> int:
        """Total across all priorities."""
        return self.low + self.medium + self.high


class ColumnCount(BaseModel):
    """How many tasks sit in one column."""

    model_config = ConfigDict(from_attributes=True)

    column_id: int
    column_name: str
    count: int


class DailyCount(BaseModel):
    """Completions on a single calendar day, for the trend sparkline."""

    date: str = Field(description="ISO date, YYYY-MM-DD.", examples=["2026-08-31"])
    count: int = 0


class BoardStats(BaseModel):
    """Aggregate view of one board.

    Scoped to a board rather than global because the app's stats screen follows
    whichever board is active -- mixing Work and Personal counts would make the
    numbers meaningless.
    """

    board_id: int
    board_name: str

    total_tasks: int = Field(description="Every task on the board, open or done.")
    open_tasks: int = Field(description="Tasks not in a done column.")
    completed_tasks: int = Field(description="Tasks in a done column, all time.")

    completed_this_week: int = Field(
        description="Completed since the most recent Monday 00:00 local time."
    )
    created_this_week: int = Field(description="Created since the most recent Monday.")

    overdue_tasks: int = Field(description="Open tasks with a due date in the past.")
    due_soon_tasks: int = Field(description="Open tasks due within the next 3 days.")

    by_priority: PriorityBreakdown = Field(
        default_factory=PriorityBreakdown,
        description="Open tasks only -- completed work is not a backlog signal.",
    )
    by_column: list[ColumnCount] = Field(default_factory=list)

    completion_trend: list[DailyCount] = Field(
        default_factory=list,
        description="Completions per day for the last 7 days, oldest first.",
    )

    top_tags: list[str] = Field(
        default_factory=list,
        description="Up to 5 most-used tags on open tasks, most frequent first.",
    )
