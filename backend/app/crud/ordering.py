"""Shared helpers for keeping ``position`` columns contiguous.

Positions are plain integers, always ``0..n-1`` with no gaps, rewritten on every
structural change.

The obvious alternative -- fractional or gapped positions, where you insert
between two cards by averaging their keys -- avoids rewriting siblings and is the
right call at scale. It is the wrong call here: a personal board holds tens of
cards, not thousands, so rewriting a column costs microseconds, and dense
integers mean the order you read is the order you see with no drift, no
rebalancing pass, and no float precision edge cases after many moves.

Every function takes a Python list already sorted by position, mutates it in
place, and writes the new indices onto the ORM objects. Callers flush/commit.
"""

from __future__ import annotations

from typing import Protocol, TypeVar


class Positioned(Protocol):
    """Anything with a mutable integer ``position``."""

    id: int
    position: int


TPositioned = TypeVar("TPositioned", bound=Positioned)


def resequence(items: list[TPositioned]) -> None:
    """Rewrite ``position`` to match list order.

    Only assigns when the value actually changes, so an unchanged reorder does
    not mark rows dirty and does not bump ``updated_at``.
    """
    for index, item in enumerate(items):
        if item.position != index:
            item.position = index


def clamp_index(index: int, length: int) -> int:
    """Constrain an insertion index to ``0..length``.

    Drag-and-drop is the reason this clamps instead of raising. A fast drop can
    arrive with an index computed from a board state the server has already moved
    past; pinning the card to the nearest valid slot is what the user meant,
    whereas a 422 would leave the card visibly stuck mid-air.
    """
    if index < 0:
        return 0
    return min(index, length)


def insert_at(items: list[TPositioned], item: TPositioned, index: int) -> None:
    """Place ``item`` at ``index`` within ``items`` and resequence.

    ``item`` may or may not already be in the list; it is removed first either
    way, so this handles both "insert new card" and "move existing card".
    """
    if item in items:
        items.remove(item)
    items.insert(clamp_index(index, len(items)), item)
    resequence(items)


def apply_explicit_order(
    items: list[TPositioned],
    ordered_ids: list[int],
) -> list[TPositioned]:
    """Reorder ``items`` to match ``ordered_ids`` and resequence.

    Ids not present in ``items`` are ignored, and any item missing from
    ``ordered_ids`` keeps its relative order at the end. Being permissive here
    matters: the client sends the order it believes in, and a card created on
    another device a moment ago should not make the whole request fail.

    Returns the reordered list.
    """
    by_id = {item.id: item for item in items}

    reordered: list[TPositioned] = []
    seen: set[int] = set()
    for item_id in ordered_ids:
        item = by_id.get(item_id)
        if item is not None and item_id not in seen:
            seen.add(item_id)
            reordered.append(item)

    # Anything the client did not mention keeps its existing relative order.
    reordered.extend(item for item in items if item.id not in seen)

    resequence(reordered)
    return reordered
