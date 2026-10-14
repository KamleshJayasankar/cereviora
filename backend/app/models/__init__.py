# Makes `from app.models import Task, TaskStatus` work cleanly.
from app.models.task import Task, TaskStatus

__all__ = ["Task", "TaskStatus"]
