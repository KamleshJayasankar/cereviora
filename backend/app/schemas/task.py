"""
CEREVIORA — Task Pydantic Schemas

Schemas are the "contract" between the API and its callers.
They define:
  - What fields are required vs optional in a request
  - What the response looks like (which fields are returned)
  - Validation rules (e.g. title must not be blank)

FastAPI uses these schemas automatically:
  - To validate incoming JSON and return 422 Unprocessable Entity on bad data
  - To serialise the response to JSON
  - To generate the /docs (Swagger) UI

Why not reuse the SQLAlchemy model directly?
  The ORM model knows about database columns, relationships and internals
  that you don't want to expose in a public API.  Pydantic schemas give you
  full control over the API surface.
"""

from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from app.models.task import TaskStatus
from app.models.task_step import StepStatus


# ── Request schemas (what the API accepts) ─────────────────────────────────────

class TaskStepCreate(BaseModel):
    """Schema for creating a step within a task."""
    step_number: int = Field(..., ge=1, description="1-based execution order.")
    title: str = Field(..., min_length=1, max_length=200, description="Step title.")
    description: str = Field(default="", max_length=5000, description="Step description.")
    step_type: str = Field(default="general", max_length=50, description="Functional type of step.")


class PlanGenerateRequest(BaseModel):
    """Optional parameters when requesting a plan."""
    custom_instructions: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional additional context or focus for the planner.",
    )


# ── Response schemas (what the API returns) ───────────────────────────────────

class TaskStepResponse(BaseModel):
    """
    A single execution step returned as part of a TaskResponse.
    """
    id: str
    task_id: str
    step_number: int
    title: str
    description: str
    step_type: str
    status: StepStatus
    result_summary: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

class TaskCreate(BaseModel):
    """
    Request body for POST /tasks.

    `Field(...)` means required.
    `Field(default=...)` means optional with a fallback value.
    `min_length` and `max_length` are validated automatically by Pydantic.
    """
    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Short, descriptive task title.",
        examples=["Prepare study plan"],
    )
    description: str = Field(
        default="",
        max_length=5000,
        description="Optional detailed description of the task.",
        examples=["Review chapters 1-5 and create action items."],
    )

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        """Reject titles that are only whitespace."""
        if not value.strip():
            raise ValueError("Title must not be blank.")
        return value.strip()  # normalise: remove leading/trailing spaces


class TaskUpdate(BaseModel):
    """
    Request body for PATCH /tasks/{task_id}.

    All fields are Optional — a PATCH should only update what is provided.
    If you send {"title": "New title"} the description is left unchanged.
    """
    title: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="New title (leave out to keep existing).",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=5000,
        description="New description (leave out to keep existing).",
    )

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError("Title must not be blank.")
        return value.strip() if value else value




class TaskResponse(BaseModel):
    """
    Full task representation returned by the API.

    `from_attributes = True` (previously called `orm_mode`) tells Pydantic
    to read values from SQLAlchemy model attributes instead of dict keys.
    Without this, `TaskResponse.model_validate(orm_task)` would fail.
    """
    id: str
    title: str
    description: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    approved_at: Optional[datetime] = None
    steps: list[TaskStepResponse] = []

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    """Paginated task list wrapper."""
    tasks: list[TaskResponse]
    total: int
    has_more: bool = False

    model_config = {"from_attributes": True}


class ExecutionRecordResponse(BaseModel):
    id: str
    task_id: str
    step_id: Optional[str] = None
    attempt: int
    event_type: str
    status: str
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None
    error_details: Optional[str] = None
    verified: bool
    verification_result: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
