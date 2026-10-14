"""
CEREVIORA — Task API Routes

These are the HTTP endpoints that clients (browser, curl, other services)
call.  Each function here is intentionally thin:
  1. Receive and validate the HTTP request (Pydantic does this automatically).
  2. Call a service function to do the actual work.
  3. Return an HTTP response with the correct status code.

Business logic lives in app/services/task_service.py, not here.

Dependency Injection:
  The `db: Session = Depends(get_db)` pattern tells FastAPI to call
  get_db(), get the session it yields, pass it to our route function,
  and then close it after the response is sent.  We never manage sessions
  manually in route handlers.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.task import TaskStatus
from app.schemas.task import TaskCreate, TaskUpdate, TaskResponse, TaskListResponse
from app.services import task_service

router = APIRouter(prefix="/tasks", tags=["Tasks"])


# ── POST /tasks ───────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,   # 201 = resource was created
    summary="Create a new task",
)
def create_task(
    data: TaskCreate,                      # FastAPI reads + validates request body
    db: Session = Depends(get_db),         # FastAPI injects the DB session
):
    """
    Create a task with a title and optional description.

    Returns the created task including its auto-generated ID and timestamps.
    """
    return task_service.create_task(db, data)


# ── GET /tasks ────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=TaskListResponse,
    summary="List all tasks",
)
def list_tasks(
    status_filter: TaskStatus | None = Query(
        default=None,
        alias="status",
        description="Filter by task status (optional).",
    ),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Return all tasks, optionally filtered by status.

    Query parameters:
    - `status` — filter by PENDING, RUNNING, SUCCEEDED, FAILED, etc.
    - `limit`  — max results (default 100, max 500).
    - `offset` — skip this many results (for pagination).
    """
    tasks, total = task_service.get_tasks(db, status_filter, limit, offset)
    return TaskListResponse(
        tasks=tasks,
        total=total,
        has_more=(offset + limit) < total,
    )


# ── GET /tasks/counts ─────────────────────────────────────────────────────────
# NOTE: this must be defined BEFORE /tasks/{task_id} so FastAPI doesn't
# try to match "counts" as a task_id UUID.

@router.get(
    "/counts",
    summary="Get task counts grouped by status (for dashboard)",
)
def task_counts(db: Session = Depends(get_db)):
    """
    Return the number of tasks in each status.
    Used by the dashboard to populate the stats cards.
    """
    return task_service.get_task_counts(db)


# ── GET /tasks/{task_id} ──────────────────────────────────────────────────────

@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Get a single task by ID",
)
def get_task(task_id: str, db: Session = Depends(get_db)):
    """
    Return a single task.  Returns 404 if the ID does not exist.
    """
    return task_service.get_task(db, task_id)


# ── PATCH /tasks/{task_id} ────────────────────────────────────────────────────

@router.patch(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Partially update a task",
)
def update_task(task_id: str, data: TaskUpdate, db: Session = Depends(get_db)):
    """
    Update only the fields provided in the request body.
    Omitted fields are left unchanged.
    Returns 404 if the task does not exist.
    """
    return task_service.update_task(db, task_id, data)


# ── DELETE /tasks/{task_id} ───────────────────────────────────────────────────

@router.delete(
    "/{task_id}",
    summary="Delete a task",
    status_code=status.HTTP_200_OK,
)
def delete_task(task_id: str, db: Session = Depends(get_db)):
    """
    Permanently delete a task and return a confirmation message.
    Returns 404 if the task does not exist.
    """
    return task_service.delete_task(db, task_id)
