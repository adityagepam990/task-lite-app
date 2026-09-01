"""Column request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import UtcDatetime
from app.schemas.task import TaskRead


class ColumnBase(BaseModel):
    """Fields a client may set on a column."""

    name: str = Field(min_length=1, max_length=120, examples=["In Progress"])
    is_done_column: bool = Field(
        default=False,
        description=(
            "Mark this as the terminal column. Tasks moved here are stamped "
            "completed, which is what the statistics screen counts."
        ),
    )

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Name cannot be empty.")
        return stripped


class ColumnCreate(ColumnBase):
    """Payload for creating a column. Appends to the board when position is omitted."""

    position: int | None = Field(default=None, ge=0)


class ColumnUpdate(BaseModel):
    """Partial update of a column."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    is_done_column: bool | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Name cannot be empty.")
        return stripped


class ColumnReorder(BaseModel):
    """Set the exact left-to-right order of a board's columns."""

    model_config = ConfigDict(extra="forbid")

    column_ids: list[int] = Field(
        min_length=1,
        description="Every column id on the board, in the desired order.",
    )


class ColumnRead(ColumnBase):
    """A column without its tasks -- used where only the lane matters."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    board_id: int
    position: int
    created_at: UtcDatetime
    updated_at: UtcDatetime


class ColumnWithTasks(ColumnRead):
    """A column including its ordered tasks.

    The board endpoint returns this so the app can render a full board from a
    single request instead of one request per column.
    """

    tasks: list[TaskRead] = Field(default_factory=list)
