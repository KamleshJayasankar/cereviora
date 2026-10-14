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
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status

from app.models.task import Task, TaskStatus
from app.models.task_step import TaskStep, StepStatus
from app.schemas.task import TaskCreate, TaskUpdate
from app.services.state_machine import validate_task_transition, InvalidStateTransitionError
from app.services.planner import get_planner, PlanPolicyError
from app.models.execution_record import ExecutionRecord
from app.services.execution_engine import execute_step


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

    # Approval covers a specific task definition. Any edits require a fresh approval.
    if task.approved_at is not None:
        task.approved_at = None

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


def plan_task(
    db: Session,
    task_id: str,
    custom_instructions: Optional[str] = None,
) -> Task:
    """
    Generate an ordered, validated execution plan for the specified task.

    Workflow:
    1. Retrieve the task or raise 404.
    2. Check state machine to verify transitioning to AWAITING_APPROVAL is valid.
    3. Generate structured steps using the deterministic planner.
    4. Remove any prior steps (idempotent replanning).
    5. Persist the new TaskStep records in the database.
    6. Transition task status to AWAITING_APPROVAL.
    7. Commit changes and return the updated Task with its steps.
    """
    task = _get_task_or_404(db, task_id)

    # 1. State machine check. Failed tasks must pass through PENDING before
    # receiving a fresh plan, matching the declared lifecycle transitions.
    try:
        if task.status == TaskStatus.FAILED:
            validate_task_transition(task.status, TaskStatus.PENDING)
            task.status = TaskStatus.PENDING
        validate_task_transition(task.status, TaskStatus.AWAITING_APPROVAL)
    except InvalidStateTransitionError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        )

    # 2. Planning with policy validation
    planner = get_planner()
    try:
        step_blueprints = planner.plan(
            title=task.title,
            description=task.description or "",
            custom_instructions=custom_instructions,
        )
    except PlanPolicyError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Plan policy validation failed: {err}",
        )

    # 3. Clear existing steps if replanning
    db.query(TaskStep).filter(TaskStep.task_id == task_id).delete()

    # 4. Create new step records
    for blueprint in step_blueprints:
        step = TaskStep(
            task_id=task.id,
            step_number=blueprint.step_number,
            title=blueprint.title,
            description=blueprint.description,
            step_type=blueprint.step_type,
            status=StepStatus.PENDING,
        )
        db.add(step)

    # 5. Transition task status
    task.status = TaskStatus.AWAITING_APPROVAL
    task.approved_at = None
    task.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(task)
    return task


def approve_task(db: Session, task_id: str) -> Task:
    """Record explicit human approval for a complete, unmodified plan."""
    task = _get_task_or_404(db, task_id)
    if task.status != TaskStatus.AWAITING_APPROVAL or not task.steps:
        raise HTTPException(status_code=400, detail="Only a planned task awaiting approval can be approved.")
    if task.approved_at is not None:
        raise HTTPException(status_code=409, detail="This plan has already been approved.")
    expected = list(range(1, len(task.steps) + 1))
    if [step.step_number for step in task.steps] != expected or any(step.status != StepStatus.PENDING for step in task.steps):
        raise HTTPException(status_code=400, detail="The task plan is incomplete or invalid and cannot be approved.")
    now = datetime.now(timezone.utc)
    task.approved_at = now
    task.updated_at = now
    db.add(ExecutionRecord(task_id=task.id, event_type="APPROVAL", status="APPROVED", output_summary="Human approval recorded for the current plan.", verified=True, verification_result="Plan order and pending step states validated.", created_at=now, completed_at=now))
    db.commit()
    db.refresh(task)
    return task


def execute_task(db: Session, task_id: str) -> Task:
    """Execute approved tasks one step at a time, persisting each outcome."""
    task = _get_task_or_404(db, task_id)
    if task.status != TaskStatus.AWAITING_APPROVAL:
        raise HTTPException(status_code=400, detail="Only a task awaiting approval can be executed.")
    if task.approved_at is None:
        raise HTTPException(status_code=403, detail="Task approval is required before execution.")
    if not task.steps or any(step.status != StepStatus.PENDING for step in task.steps):
        raise HTTPException(status_code=400, detail="Task plan is incomplete or has already been executed.")

    try:
        validate_task_transition(task.status, TaskStatus.RUNNING)
    except InvalidStateTransitionError as err:
        raise HTTPException(status_code=400, detail=str(err))
    task.status = TaskStatus.RUNNING
    task.updated_at = datetime.now(timezone.utc)
    db.commit()

    for step in task.steps:
        now = datetime.now(timezone.utc)
        previous_attempts = db.query(ExecutionRecord).filter(ExecutionRecord.step_id == step.id, ExecutionRecord.event_type == "STEP").count()
        record = ExecutionRecord(task_id=task.id, step_id=step.id, attempt=previous_attempts + 1, event_type="STEP", status="RUNNING", input_summary=f"{step.step_type}: {step.title}", created_at=now)
        step.status = StepStatus.RUNNING
        db.add(record)
        db.commit()
        try:
            output, verified, verification = execute_step(db, task, step)
            if step.step_type == "verify" and not verified:
                raise RuntimeError("Final database verification did not pass.")
            step.status = StepStatus.SUCCEEDED
            step.result_summary = output
            step.error_message = None
            step.completed_at = datetime.now(timezone.utc)
            record.status = "SUCCEEDED"
            record.output_summary = output
            record.verified = verified
            record.verification_result = verification
            record.completed_at = step.completed_at
            db.commit()
        except Exception as err:
            db.rollback()
            step = db.query(TaskStep).filter(TaskStep.id == step.id).one()
            record = db.query(ExecutionRecord).filter(ExecutionRecord.id == record.id).one()
            step.status = StepStatus.FAILED
            step.error_message = str(err)[:2000]
            step.completed_at = datetime.now(timezone.utc)
            record.status = "FAILED"
            record.error_details = str(err)[:2000]
            record.verified = False
            record.verification_result = "Execution failed before successful verification."
            record.completed_at = step.completed_at
            task = db.query(Task).filter(Task.id == task_id).one()
            task.status = TaskStatus.FAILED
            task.updated_at = step.completed_at
            db.commit()
            db.refresh(task)
            return task

    task = db.query(Task).filter(Task.id == task_id).one()
    task.status = TaskStatus.SUCCEEDED
    task.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(task)
    return task


def get_task_history(db: Session, task_id: str) -> list[ExecutionRecord]:
    _get_task_or_404(db, task_id)
    return db.query(ExecutionRecord).filter(ExecutionRecord.task_id == task_id).order_by(ExecutionRecord.created_at, ExecutionRecord.id).all()
