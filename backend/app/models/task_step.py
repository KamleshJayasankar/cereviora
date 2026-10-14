"""
CEREVIORA — TaskStep ORM Model

This file defines the 'task_steps' table in SQLite using SQLAlchemy ORM.

Each task is planned into an ordered sequence of discrete steps.
For example, a task "Prepare study plan" might have 5 steps:
  1. Interpret request and extract learning objectives
  2. Synthesize curriculum outline
  3. Extract actionable study milestones
  4. Save study plan to database
  5. Verify record persistence and integrity

Step Status Lifecycle:
  PENDING   → Step planned but not yet executed.
  RUNNING   → Step actively executing in the execution engine.
  SUCCEEDED → Step executed and verified.
  FAILED    → Step failed or verification failed.
  SKIPPED   → Step bypassed due to prior step failure or policy.
"""

import uuid
from datetime import datetime, timezone
import enum
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.database import Base


class StepStatus(str, enum.Enum):
    """Execution status for an individual step."""
    PENDING   = "PENDING"
    RUNNING   = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED    = "FAILED"
    SKIPPED   = "SKIPPED"


class TaskStep(Base):
    """
    SQLAlchemy ORM model representing a single step within a task's plan.
    """
    __tablename__ = "task_steps"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )

    task_id = Column(
        String(36),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 1-indexed execution order within the task (Step 1, Step 2, etc.)
    step_number = Column(Integer, nullable=False)

    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True, default="")

    # The functional operation category (e.g., 'interpret', 'research', 'generate', 'extract', 'save', 'verify')
    step_type = Column(String(50), nullable=False, default="general")

    status = Column(
        SAEnum(StepStatus),
        nullable=False,
        default=StepStatus.PENDING,
        index=True,
    )

    result_summary = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationship to parent task
    task = relationship("Task", back_populates="steps")

    def __repr__(self) -> str:
        return f"<TaskStep id={self.id!r} step_number={self.step_number} title={self.title!r} status={self.status}>"
