"""Task request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import Priority
from app.schemas.common import UtcDatetime

# Tag hygiene, applied on both create and update. Without this you end up with
# "work", "Work" and " work " as three distinct tags in the filter UI.
MAX_TAGS = 20
MAX_TAG_LENGTH = 24


def _normalise_tags(tags: list[str]) -> list[str]:
    """Trim, drop blanks, lowercase, and de-duplicate while preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for raw in tags:
        tag = raw.strip().lower()
        if not tag or tag in seen:
            continue
        seen.add(tag)
        result.append(tag[:MAX_TAG_LENGTH])
    return result[:MAX_TAGS]


class TaskBase(BaseModel):
    """Fields a client may set on a task."""

    title: str = Field(min_length=1, max_length=200, examples=["Buy milk"])
    description: str | None = Field(default=None, max_length=10_000)
    priority: Priority = Priority.MEDIUM
    due_date: UtcDatetime | None = Field(
        default=None,
        description="ISO-8601 timestamp. Naive values are interpreted as UTC.",
    )
    tags: list[str] = Field(default_factory=list, examples=[["errand", "home"]])

    @field_validator("title")
    @classmethod
    def _strip_title(cls, value: str) -> str:
        """Reject titles that are only whitespace."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("Title cannot be empty.")
        return stripped

    @field_validator("description")
    @classmethod
    def _blank_description_is_none(cls, value: str | None) -> str | None:
        """Treat an empty description as absent, so the UI can skip the section."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("tags")
    @classmethod
    def _clean_tags(cls, value: list[str]) -> list[str]:
        return _normalise_tags(value)


class TaskCreate(TaskBase):
    """Payload for creating a task.

    ``column_id`` is a path parameter on the nested route
    (``POST /api/columns/{column_id}/tasks``) and a body field on the flat route
    (``POST /api/tasks``), hence optional here.
    """

    column_id: int | None = Field(
        default=None,
        description="Target column. Required on POST /api/tasks; ignored on the nested route.",
    )
    position: int | None = Field(
        default=None,
        ge=0,
        description="Insertion index within the column. Appends when omitted.",
    )


class TaskUpdate(BaseModel):
    """Partial update. Omitted fields are left unchanged.

    Note the difference between omitted and null: omitting ``due_date`` keeps the
    existing date, while sending ``null`` clears it. Routers rely on
    ``model_dump(exclude_unset=True)`` to tell these apart.
    """

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    priority: Priority | None = None
    due_date: datetime | None = None
    tags: list[str] | None = None

    @field_validator("title")
    @classmethod
    def _strip_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Title cannot be empty.")
        return stripped

    @field_validator("description")
    @classmethod
    def _blank_description_is_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("tags")
    @classmethod
    def _clean_tags(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _normalise_tags(value)


class TaskMove(BaseModel):
    """Move a task to a column and/or a new index within it.

    This is the endpoint drag-and-drop calls on drop. ``position`` is the index
    the card should occupy *after* the move; the server clamps out-of-range
    values rather than erroring, because a fast drag can race the UI's own count.
    """

    model_config = ConfigDict(extra="forbid")

    column_id: int = Field(description="Destination column id.")
    position: int = Field(default=0, ge=0, description="Destination index, 0-based.")


class TaskReorder(BaseModel):
    """Set the exact order of tasks within a single column."""

    model_config = ConfigDict(extra="forbid")

    task_ids: list[int] = Field(
        min_length=1,
        description="Every task id in the column, in the desired order.",
    )


class TaskRead(TaskBase):
    """A task as returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    column_id: int
    position: int
    is_completed: bool
    completed_at: UtcDatetime | None
    created_at: UtcDatetime
    updated_at: UtcDatetime
