"""Starter content for a fresh database.

A brand-new install with three empty boards is hard to evaluate -- you cannot
tell whether drag-and-drop works without something to drag. So the first run
creates the three boards from the spec plus a handful of realistic cards spread
across columns, priorities and due dates.

Seeding is skipped whenever any board already exists, so this can never
overwrite real data. Disable it entirely with ``[seed] enabled = false``.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Board, Column, Priority, Task
from app.utils.time import start_of_day, utcnow

logger = logging.getLogger(__name__)

# (name, is_done_column) for the four standard lanes.
_LANES: tuple[tuple[str, bool], ...] = (
    ("Backlog", False),
    ("To Do", False),
    ("In Progress", False),
    ("Done", True),
)

# Per board: accent colour, description, and the cards to place.
# Each card is (lane index, title, priority, tags, due-date offset in days).
# A None offset means no due date; negative offsets are deliberately overdue so
# the overdue badge and the stats screen have something to show.
_SEED: dict[str, dict[str, object]] = {
    "Personal": {
        "color": "#6366F1",
        "description": "Life admin, errands and everything outside work.",
        "cards": [
            (0, "Plan weekend hike", Priority.LOW, ["outdoors"], 12),
            (1, "Renew passport", Priority.HIGH, ["admin", "urgent"], 5),
            (1, "Book dentist appointment", Priority.MEDIUM, ["health"], -2),
            (2, "Read 'The Pragmatic Programmer'", Priority.LOW, ["reading"], None),
            (3, "Pay electricity bill", Priority.HIGH, ["admin", "finance"], -6),
        ],
    },
    "Work": {
        "color": "#0EA5E9",
        "description": "Sprint work, reviews and meeting follow-ups.",
        "cards": [
            (0, "Investigate flaky integration test", Priority.MEDIUM, ["testing"], None),
            (1, "Write Q3 planning doc", Priority.HIGH, ["writing", "urgent"], 2),
            (1, "Review PR #482", Priority.MEDIUM, ["review"], 1),
            (2, "Migrate auth service to new SDK", Priority.HIGH, ["backend"], 9),
            (2, "Pair on onboarding flow", Priority.LOW, ["frontend"], None),
            (3, "Ship release 1.4.0", Priority.HIGH, ["release"], -1),
            (3, "Close out sprint retro actions", Priority.LOW, ["process"], -4),
        ],
    },
    "Side Projects": {
        "color": "#F59E0B",
        "description": "Things built for the fun of it.",
        "cards": [
            (0, "Sketch out CLI for note-taking tool", Priority.LOW, ["idea"], None),
            (1, "Buy domain name", Priority.MEDIUM, ["admin"], 20),
            (2, "Build Kanban app", Priority.HIGH, ["react-native", "fastapi"], 3),
            (3, "Set up CI pipeline", Priority.MEDIUM, ["devops"], -8),
        ],
    },
}


def seed_if_empty(db: Session) -> bool:
    """Populate starter boards when the database has none.

    Returns True if seeding ran, False if existing data was left alone.
    """
    existing = db.scalars(select(Board).limit(1)).first()
    if existing is not None:
        return False

    now = utcnow()

    for index, (board_name, spec) in enumerate(_SEED.items()):
        lanes = [
            Column(name=name, position=position, is_done_column=is_done)
            for position, (name, is_done) in enumerate(_LANES)
        ]

        board = Board(
            name=board_name,
            description=str(spec["description"]),
            color=str(spec["color"]),
            position=index,
            # Personal is first in the dict and becomes the board the app opens on.
            is_active=index == 0,
            columns=lanes,
        )

        # Track the next free slot per lane so seeded cards get contiguous
        # positions, matching the invariant the rest of the app relies on.
        next_position = [0] * len(lanes)

        for lane_index, title, priority, tags, due_offset in spec["cards"]:  # type: ignore[misc]
            lane = lanes[lane_index]
            task = Task(
                title=title,
                priority=priority,
                tags=list(tags),
                position=next_position[lane_index],
                due_date=(
                    start_of_day(now) + timedelta(days=due_offset, hours=18)
                    if due_offset is not None
                    else None
                ),
            )
            # Cards seeded into the Done lane must look genuinely completed, or
            # the stats screen opens with a completion count of zero.
            if lane.is_done_column:
                task.is_completed = True
                # Stagger completion times across the past few days so the trend
                # sparkline is not a single spike.
                task.completed_at = now - timedelta(days=next_position[lane_index], hours=3)

            lane.tasks.append(task)
            next_position[lane_index] += 1

        db.add(board)

    db.commit()
    logger.info("seeded %d starter boards", len(_SEED))
    return True
