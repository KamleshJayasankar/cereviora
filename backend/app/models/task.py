"""
CEREVIORA — Task ORM Model

This file defines the 'tasks' table in SQLite using SQLAlchemy's ORM
(Object-Relational Mapper).

What is an ORM?
  Instead of writing raw SQL like:
    CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT NOT NULL ...)
  we describe the table as a Python class.  SQLAlchemy translates that
  class into the appropriate SQL for our database.

What is a model?
  A model class (e.g. Task) represents one row in the database table.
  Each attribute on the class corresponds to one column.

Why UUIDs instead of auto-incrementing integers?
  Auto-increment IDs (1, 2, 3…) are predictable.  Anyone who knows task
  ID 5 can guess that task 4 and 6 also exist, which is a security risk.
  UUIDs are 128-bit random strings like 'a3f7c2d1-...' — they are
  statistically impossible to guess.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Text, Enum as SAEnum
from sqlalchemy.orm import relationship
import enum
from app.database import Base


class TaskStatus(str, enum.Enum):
    """
    The lifecycle states a task can be in.

    We use Python's enum so that only valid states can be stored.
    The `str` mixin means the enum values ARE strings — handy for JSON
    serialisation and for comparing with plain strings.

    PENDING          → Task exists but no plan has been generated yet.
    AWAITING_APPROVAL→ A plan exists and needs human sign-off before execution.
    RUNNING          → Steps are actively being executed.
    SUCCEEDED        → All steps completed and their results were verified.
    FAILED           → At least one step failed or verification failed.
    """
    PENDING           = "PENDING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    RUNNING           = "RUNNING"
    SUCCEEDED         = "SUCCEEDED"
    FAILED            = "FAILED"


class Task(Base):
    """
    SQLAlchemy ORM model representing the 'tasks' table.

    Each instance of this class = one row in the database.
    """

    __tablename__ = "tasks"

    # Primary key: a UUID stored as a plain string.
    # `default=` runs automatically when you create a new Task object —
    # you never need to generate IDs yourself.
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )

    # Task title: required, maximum 200 characters.
    # nullable=False means the database will reject rows without a title.
    title = Column(String(200), nullable=False)

    # Task description: optional long text.
    description = Column(Text, nullable=True, default="")

    # Current lifecycle state.
    # SAEnum stores the string value of the enum in the database.
    status = Column(
        SAEnum(TaskStatus),
        nullable=False,
        default=TaskStatus.PENDING,
        index=True,        # indexed so filtering by status is fast
    )

    # Timestamps stored in UTC.  Always use UTC in the database — convert
    # to local time only at the display layer.
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationship to child task steps, automatically ordered by step_number.
    # cascade="all, delete-orphan" ensures when a Task is deleted, all its steps are also deleted.
    steps = relationship(
        "TaskStep",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="TaskStep.step_number",
    )

    def __repr__(self) -> str:
        """Useful string representation for debugging."""
        return f"<Task id={self.id!r} title={self.title!r} status={self.status}>"
