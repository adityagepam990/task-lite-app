"""Persistence logic.

Routers stay thin: they validate input, call one function from here, broadcast an
event and wrap the result in an envelope. All ordering bookkeeping and all
cross-entity invariants (single active board, completion stamping, contiguous
positions) live in this package so they are enforced regardless of which route
was used.
"""

from app.crud import boards, columns, stats, tasks

__all__ = ["boards", "columns", "stats", "tasks"]
