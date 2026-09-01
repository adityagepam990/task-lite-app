"""ORM models.

Imported as a package so that ``from app import models`` registers every mapper
on ``Base.metadata`` -- which is what lets :func:`app.database.create_all` see
all three tables. Relationships reference each other by class *name* (a string),
so import order between these modules does not matter.
"""

from app.models.board import Board
from app.models.column import Column
from app.models.enums import Priority
from app.models.task import Task

__all__ = ["Board", "Column", "Priority", "Task"]
