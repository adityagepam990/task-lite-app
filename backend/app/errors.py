"""Typed application errors and their translation into HTTP responses.

Every failure the client can see leaves through here, which is what makes the
error half of the response envelope consistent. Business logic raises a
subclass of :class:`AppError` and never builds an HTTP response itself.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base class for expected, client-facing failures.

    Attributes:
        message: Human-readable description, safe to display in the UI.
        code: Stable machine-readable identifier the frontend can branch on.
        status_code: HTTP status to respond with.
        details: Optional structured context (e.g. which field was invalid).
    """

    code: str = "error"
    status_code: int = 400

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.details = details


class NotFoundError(AppError):
    """A requested entity does not exist."""

    code = "not_found"
    status_code = 404

    @classmethod
    def for_entity(cls, entity: str, entity_id: int | str) -> "NotFoundError":
        """Build a consistently worded 404 for a missing record."""
        return cls(
            f"{entity} {entity_id} was not found.",
            details={"entity": entity.lower(), "id": entity_id},
        )


class ValidationError(AppError):
    """A request was well-formed but semantically invalid.

    Used for rules Pydantic cannot express on its own -- for instance moving a
    task into a column that belongs to a different board.
    """

    code = "validation_error"
    status_code = 422


class ConflictError(AppError):
    """The request collides with the current state of the data."""

    code = "conflict"
    status_code = 409
