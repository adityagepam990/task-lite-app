"""Time handling, with one rule: **everything is stored as naive UTC.**

SQLite has no timezone-aware datetime type. SQLAlchemy's SQLite ``DATETIME``
formats the year/month/day/hour/... fields of whatever it is handed and silently
drops ``tzinfo``, so writing a ``+05:30`` datetime would persist the local wall
clock while every reader assumes UTC -- a five-and-a-half hour bug that only
shows up for users outside UTC.

The fix is to normalise on the way in (:func:`to_naive_utc`) and to re-attach the
UTC offset on the way out (``UtcDatetime`` in :mod:`app.schemas.common`), so the
JSON a client sees always carries an explicit ``Z``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def utcnow() -> datetime:
    """Return the current UTC time as a naive datetime, ready to store."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_naive_utc(value: datetime | None) -> datetime | None:
    """Normalise a client-supplied datetime for storage.

    An aware datetime is converted to UTC and stripped of ``tzinfo``. A naive one
    is assumed to already be UTC and returned unchanged -- the API documents
    ISO-8601 input, and guessing a client's local zone would be worse than
    stating the assumption.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def start_of_week(reference: datetime | None = None) -> datetime:
    """Return midnight on the Monday of ``reference``'s week, in naive UTC.

    "This week" in the statistics screen means Monday-to-now, which matches how
    most people think about a work week.
    """
    now = reference or utcnow()
    monday = now - timedelta(days=now.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def start_of_day(reference: datetime | None = None) -> datetime:
    """Return midnight of ``reference``'s day, in naive UTC."""
    now = reference or utcnow()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)
