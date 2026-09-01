"""Enumerations shared by models and schemas."""

from __future__ import annotations

from enum import Enum


class Priority(str, Enum):
    """Task priority.

    Inherits from ``str`` so the value serialises as ``"high"`` rather than
    ``Priority.HIGH``, and so SQLAlchemy stores a readable string in SQLite.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def sort_weight(self) -> int:
        """Rank for "most important first" ordering.

        Used by the statistics endpoint; defined here so the ordering lives with
        the enum instead of being re-derived by each caller.
        """
        return {Priority.LOW: 0, Priority.MEDIUM: 1, Priority.HIGH: 2}[self]
