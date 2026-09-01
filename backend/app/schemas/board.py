"""Board request/response schemas."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.column import ColumnWithTasks
from app.schemas.common import UtcDatetime

# #RGB, #RRGGBB or #RRGGBBAA.
HEX_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")

DEFAULT_BOARD_COLOR = "#6366F1"


class BoardBase(BaseModel):
    """Fields a client may set on a board."""

    name: str = Field(min_length=1, max_length=120, examples=["Personal"])
    description: str | None = Field(default=None, max_length=500)
    color: str = Field(default=DEFAULT_BOARD_COLOR, examples=["#6366F1"])

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Name cannot be empty.")
        return stripped

    @field_validator("description")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("color")
    @classmethod
    def _validate_color(cls, value: str) -> str:
        """Accept only hex colours, normalised to uppercase.

        Validated here rather than in the UI so a hand-rolled API call cannot
        store something the frontend will fail to parse.
        """
        candidate = value.strip()
        if not HEX_COLOR.match(candidate):
            raise ValueError(
                "Color must be a hex value such as #6366F1, #FFF or #6366F1CC."
            )
        return candidate.upper()


class BoardCreate(BoardBase):
    """Payload for creating a board.

    ``with_default_columns`` is a convenience for the app's "new board" flow: a
    board with no columns cannot show anything, so the default is to scaffold the
    usual four lanes.
    """

    with_default_columns: bool = Field(
        default=True,
        description="Create Backlog / To Do / In Progress / Done alongside the board.",
    )
    make_active: bool = Field(
        default=False,
        description="Switch to this board immediately after creating it.",
    )


class BoardUpdate(BaseModel):
    """Partial update of a board."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    color: str | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Name cannot be empty.")
        return stripped

    @field_validator("description")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("color")
    @classmethod
    def _validate_color(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = value.strip()
        if not HEX_COLOR.match(candidate):
            raise ValueError(
                "Color must be a hex value such as #6366F1, #FFF or #6366F1CC."
            )
        return candidate.upper()


class BoardReorder(BaseModel):
    """Set the order boards appear in the switcher."""

    model_config = ConfigDict(extra="forbid")

    board_ids: list[int] = Field(min_length=1, description="Every board id, in order.")


class BoardRead(BoardBase):
    """A board without its columns -- used for the board list."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    position: int
    created_at: UtcDatetime
    updated_at: UtcDatetime


class BoardWithColumns(BoardRead):
    """A board with its full column and task tree.

    Returned by ``GET /api/boards/{id}`` and ``GET /api/boards/active``, which is
    the single request the app makes on launch and on pull-to-refresh.
    """

    columns: list[ColumnWithTasks] = Field(default_factory=list)
