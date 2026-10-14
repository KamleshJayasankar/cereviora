"""
CEREVIORA — State Machine & Lifecycle Transitions

This module implements the formal state machine governing Task and Step
lifecycle transitions.

Why a state machine?
  In mission-critical automation, an operation should never jump straight from
  PENDING to SUCCEEDED without being planned, approved, and executed.
  The state machine enforces this policy strictly by maintaining an explicit
  allowlist of valid (from_state -> to_state) transitions. Any illegal transition
  is rejected immediately.

Valid Task Transitions:
  PENDING           → AWAITING_APPROVAL (when structured plan is generated)
  AWAITING_APPROVAL → RUNNING           (when human approves execution)
  AWAITING_APPROVAL → PENDING           (when plan is cancelled or replanned)
  RUNNING           → SUCCEEDED         (when all steps succeed and verify)
  RUNNING           → FAILED            (when any step or verification fails)
  FAILED            → PENDING           (when task is reset or replanned)
  SUCCEEDED         → PENDING           (when task is explicitly reset for re-run)

Any other transition (e.g., PENDING → RUNNING, PENDING → SUCCEEDED) is forbidden.
"""

from app.models.task import TaskStatus
from app.models.task_step import StepStatus


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal lifecycle state transition is attempted."""
    def __init__(self, entity_type: str, current_state: str, target_state: str, allowed: list[str]):
        self.entity_type = entity_type
        self.current_state = current_state
        self.target_state = target_state
        self.allowed = allowed
        msg = (
            f"Invalid {entity_type} state transition from '{current_state}' to '{target_state}'. "
            f"Allowed target states from '{current_state}': {allowed if allowed else 'None (terminal state)'}."
        )
        super().__init__(msg)


# Allowlist mapping: current_state -> set of valid target states
TASK_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {
        TaskStatus.AWAITING_APPROVAL,
    },
    TaskStatus.AWAITING_APPROVAL: {
        TaskStatus.RUNNING,
        TaskStatus.PENDING,  # allow replanning/reset
    },
    TaskStatus.RUNNING: {
        TaskStatus.SUCCEEDED,
        TaskStatus.FAILED,
    },
    TaskStatus.FAILED: {
        TaskStatus.PENDING,  # allow replanning/reset
    },
    TaskStatus.SUCCEEDED: {
        TaskStatus.PENDING,  # allow intentional reset
    },
}

STEP_TRANSITIONS: dict[StepStatus, set[StepStatus]] = {
    StepStatus.PENDING: {
        StepStatus.RUNNING,
        StepStatus.SKIPPED,
    },
    StepStatus.RUNNING: {
        StepStatus.SUCCEEDED,
        StepStatus.FAILED,
    },
    StepStatus.FAILED: {
        StepStatus.PENDING,  # retry
    },
    StepStatus.SKIPPED: {
        StepStatus.PENDING,
    },
    StepStatus.SUCCEEDED: set(),  # terminal
}


def can_transition_task(current: TaskStatus, target: TaskStatus) -> bool:
    """Return True if the task state transition is permitted, False otherwise."""
    if current == target:
        return True  # idempotent transition to same status
    return target in TASK_TRANSITIONS.get(current, set())


def validate_task_transition(current: TaskStatus, target: TaskStatus) -> None:
    """
    Validate that the transition from `current` to `target` is allowed.
    Raises InvalidStateTransitionError if the transition is illegal.
    """
    if not can_transition_task(current, target):
        allowed = [s.value for s in TASK_TRANSITIONS.get(current, set())]
        raise InvalidStateTransitionError("Task", current.value, target.value, allowed)


def can_transition_step(current: StepStatus, target: StepStatus) -> bool:
    """Return True if the step state transition is permitted, False otherwise."""
    if current == target:
        return True
    return target in STEP_TRANSITIONS.get(current, set())


def validate_step_transition(current: StepStatus, target: StepStatus) -> None:
    """
    Validate that the transition from `current` to `target` is allowed.
    Raises InvalidStateTransitionError if the transition is illegal.
    """
    if not can_transition_step(current, target):
        allowed = [s.value for s in STEP_TRANSITIONS.get(current, set())]
        raise InvalidStateTransitionError("TaskStep", current.value, target.value, allowed)
