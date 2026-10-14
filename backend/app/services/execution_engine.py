"""Runs fixed, reviewed operations. Plan text is treated only as data."""
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.task import Task
from app.models.task_step import TaskStep
from app.models.task_artifact import TaskArtifact


class ExecutionPolicyError(ValueError):
    pass


def _describe(task: Task, action: str) -> str:
    # This application currently has no external research/model integration.
    # These handlers produce bounded text from task data and never interpret it as code.
    return f"{action}: {task.title}. Context: {(task.description or '').strip()[:1000]}"[:2000]


def execute_step(db: Session, task: Task, step: TaskStep) -> tuple[str, bool, str]:
    """Dispatch by exact step_type. Unknown/future planner output fails closed."""
    handlers = {
        "interpret": lambda: _describe(task, "Requirements interpreted"),
        "research": lambda: _describe(task, "Research notes prepared from supplied context"),
        "generate": lambda: _describe(task, "Draft generated"),
        "extract": lambda: _describe(task, "Action items extracted"),
        "general": lambda: _describe(task, "Safe task summary prepared"),
    }
    if step.step_type == "save":
        content = _describe(task, "Task plan")
        db.add(TaskArtifact(task_id=task.id, content=content))
        db.flush()
        return f"Saved task artifact ({len(content)} characters).", True, "Artifact row was written to the database."
    if step.step_type == "verify":
        # Verify persisted state directly, after prior steps have committed.
        artifact = db.query(TaskArtifact).filter(TaskArtifact.task_id == task.id).order_by(TaskArtifact.created_at.desc()).first()
        persisted_steps = db.query(TaskStep).filter(TaskStep.task_id == task.id).count()
        successful_steps = db.query(TaskStep).filter(TaskStep.task_id == task.id, TaskStep.status == "SUCCEEDED").count()
        if artifact is None or persisted_steps != len(task.steps) or successful_steps != len(task.steps) - 1:
            raise ExecutionPolicyError("Database verification failed: expected a task artifact and all earlier steps in succeeded state.")
        return f"Verified {persisted_steps} persisted steps and task artifact.", True, "Database query confirmed the artifact and all earlier steps in succeeded state."
    handler = handlers.get(step.step_type)
    if handler is None:
        raise ExecutionPolicyError(f"No allowlisted operation for step type '{step.step_type}'.")
    return handler(), False, "Allowlisted local operation completed; final database verification is performed by the verify step."
