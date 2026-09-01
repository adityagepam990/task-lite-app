"""The response envelope shared by every endpoint.

Success and failure have the same outer shape, differing only in which of
``data``/``error`` is populated:

    {"success": true,  "data": {...},          "error": null}
    {"success": false, "data": null,           "error": {"code": ..., ...}}

One envelope means the frontend has exactly one place that unwraps a response
and exactly one place that turns a failure into an ``ApiError`` -- see
``frontend/src/api/client.ts``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

T = TypeVar("T")


def _as_utc_iso(value: datetime) -> str:
    """Serialise a stored datetime as an explicit-UTC ISO-8601 string.

    Timestamps are stored naive-UTC (see :mod:`app.utils.time`). Emitting them
    without an offset would be actively harmful: JavaScript parses
    ``"2026-08-31T12:00:00"`` as *local* time but ``"...Z"`` as UTC, so a naive
    string would shift every date in the UI by the client's offset.
    """
    aware = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    return aware.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# Use in place of ``datetime`` on any field that is read back by a client.
# Parsing is unchanged (Pydantic still accepts any ISO-8601 input); only JSON
# serialisation is customised, so Python-mode dumps still yield datetimes.
UtcDatetime = Annotated[
    datetime,
    PlainSerializer(_as_utc_iso, return_type=str, when_used="json"),
]


class ErrorBody(BaseModel):
    """Machine- and human-readable description of a failure."""

    code: str = Field(
        description="Stable identifier, e.g. 'not_found'. Safe to branch on.",
        examples=["not_found"],
    )
    message: str = Field(
        description="Human-readable message, safe to show in the UI.",
        examples=["Task 42 was not found."],
    )
    details: Any | None = Field(
        default=None,
        description="Optional structured context, e.g. per-field validation errors.",
    )


class ApiResponse(BaseModel, Generic[T]):
    """Envelope for a successful response carrying a payload of type ``T``."""

    model_config = ConfigDict(from_attributes=True)

    success: bool = True
    data: T
    error: None = None

    @classmethod
    def ok(cls, data: T) -> "ApiResponse[T]":
        """Wrap ``data`` in a success envelope."""
        return cls(data=data)


class ErrorResponse(BaseModel):
    """Envelope for a failed response.

    Declared separately from :class:`ApiResponse` (rather than making ``data``
    optional) so that ``ApiResponse[TaskRead].data`` is non-optional for clients
    generating types from the OpenAPI schema.
    """

    success: bool = False
    data: None = None
    error: ErrorBody
