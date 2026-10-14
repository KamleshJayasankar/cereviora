"""
CEREVIORA — Task Service

This module contains all the business logic for task management.
It has no knowledge of HTTP — it only knows about databases and
Python objects.

Why keep this separate from the API routes?
  - You can unit-test business logic without starting an HTTP server.
  - Multiple routes can call the same service function.
  - The code is easier to read when HTTP concerns and data concerns
    are not mixed together.

All functions accept a SQLAlchemy session (db) as a parameter.
The session is created per-request in the route handler and passed
down here.  This is called "dependency injection" — the function does
not create its own database connection, it receives one.
"""

from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status

from app.models.task import Task, TaskStatus
from app.schemas.task import TaskCreate, TaskUpdate


# ── Helper ────────────────────────────────────────────────────────────────────

def _get_task_or_404(db: Session, task_id: str) -> Task:
    """
    Fetch a task by ID, or raise HTTP 404 if it doesn't exist.

    This is a private helper (starts with _) used by multiple functions below.
    We always handle the "not found" case explicitly so that callers never
    have to check for None — they either get a Task object or an exception.
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found.",
        )
    return task


# ── CRUD operations ───────────────────────────────────────────────────────────

def create_task(db: Session, data: TaskCreate) -> Task:
    """
    Insert a new task row into the database.

    Steps:
    1. Create a Task ORM object from the validated Pydantic data.
    2. Add it to the database session (marks it for insertion).
    3. Commit — this is the moment the SQL INSERT actually runs.
    4. Refresh — re-reads the row from the database so we get the
       server-generated defaults (timestamps, auto-generated IDs).
    5. Return the populated Task object.
    """
    task = Task(
        title=data.title,
        description=data.description,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def get_tasks(
    db: Session,
    status_filter: TaskStatus | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Task], int]:
    """
    Return a paginated list of tasks and the total count.

    Parameters
    ----------
    db            : Active database session.
    status_filter : If provided, only return tasks with this status.
    limit         : Maximum number of rows to return (for pagination).
    offset        : Number of rows to skip (for pagination).

    Returns a (tasks, total) tuple so the caller can build a response
    that includes `has_more` without a second database round-trip.
    """
    query = db.query(Task)

    if status_filter is not None:
        query = query.filter(Task.status == status_filter)

    total: int = query.count()
    tasks: list[Task] = (
        query
        .order_by(Task.created_at.desc())  # newest first
        .offset(offset)
        .limit(limit)
        .all()
    )
    return tasks, total


def get_task(db: Session, task_id: str) -> Task:
    """Return a single task by ID, or raise 404."""
    return _get_task_or_404(db, task_id)


def update_task(db: Session, task_id: str, data: TaskUpdate) -> Task:
    """
    Update only the fields that were provided in the PATCH body.

    PATCH (partial update) is different from PUT (full replacement).
    With PATCH, a client sends only the fields it wants to change.
    `data.model_dump(exclude_unset=True)` returns a dict of only the
    fields the client actually included in the request body — fields
    that were not sent are excluded.

    This prevents accidentally clearing a field because the client
    omitted it.
    """
    task = _get_task_or_404(db, task_id)

    updates = data.model_dump(exclude_unset=True)
    if not updates:
        # Client sent an empty body — nothing to do, return as-is
        return task

    for field, value in updates.items():
        setattr(task, field, value)

    # Manually set updated_at because SQLAlchemy's onupdate only fires
    # during SQL UPDATE statements, not when we use setattr.
    task.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, task_id: str) -> dict:
    """
    Permanently delete a task.

    Design decision: we delete immediately and return a confirmation
    message.  In a production system you might use soft-delete (set a
    deleted_at timestamp) to preserve audit history.  For CEREVIORA's
    scope, hard delete is acceptable.

    Related execution records are out of scope for Day 2 — they will be
    handled by cascade rules in Day 4.
    """
    task = _get_task_or_404(db, task_id)
    db.delete(task)
    db.commit()
    return {"message": f"Task '{task_id}' deleted successfully."}


def get_task_counts(db: Session) -> dict[str, int]:
    """
    Return counts grouped by status — used by the dashboard.

    `func.count()` generates SQL COUNT() — much faster than loading all
    rows into Python and counting with len().
    """
    rows = (
        db.query(Task.status, func.count(Task.id))
        .group_by(Task.status)
        .all()
    )
    counts: dict[str, int] = {s.value: 0 for s in TaskStatus}
    for task_status, count in rows:
        counts[task_status.value] = count
    counts["total"] = sum(counts.values())
    return counts
