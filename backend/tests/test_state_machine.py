"""
CEREVIORA — Tests: State Machine & Lifecycle Transitions

Tests verify that:
1. Permitted task transitions succeed.
2. Forbidden task transitions raise InvalidStateTransitionError.
3. Permitted step transitions succeed.
4. Forbidden step transitions raise InvalidStateTransitionError.
5. Idempotent transitions (same state to same state) succeed.
"""

import pytest
from app.models.task import TaskStatus
from app.models.task_step import StepStatus
from app.services.state_machine import (
    validate_task_transition,
    validate_step_transition,
    can_transition_task,
    can_transition_step,
    InvalidStateTransitionError,
)


class TestTaskStateMachine:

    def test_valid_task_lifecycle_flow(self):
        """Happy path progression: PENDING -> AWAITING_APPROVAL -> RUNNING -> SUCCEEDED."""
        assert can_transition_task(TaskStatus.PENDING, TaskStatus.AWAITING_APPROVAL) is True
        assert can_transition_task(TaskStatus.AWAITING_APPROVAL, TaskStatus.RUNNING) is True
        assert can_transition_task(TaskStatus.RUNNING, TaskStatus.SUCCEEDED) is True

    def test_failure_transition(self):
        """RUNNING can transition to FAILED."""
        assert can_transition_task(TaskStatus.RUNNING, TaskStatus.FAILED) is True

    def test_reset_from_failed(self):
        """FAILED can be reset back to PENDING for replanning."""
        assert can_transition_task(TaskStatus.FAILED, TaskStatus.PENDING) is True

    def test_cancel_plan_to_pending(self):
        """AWAITING_APPROVAL can be reset back to PENDING."""
        assert can_transition_task(TaskStatus.AWAITING_APPROVAL, TaskStatus.PENDING) is True

    def test_idempotent_task_transition(self):
        """Staying in the same state is always permitted."""
        for status in TaskStatus:
            assert can_transition_task(status, status) is True
            validate_task_transition(status, status)  # does not raise

    def test_illegal_jump_to_running(self):
        """PENDING cannot jump straight to RUNNING without approval."""
        assert can_transition_task(TaskStatus.PENDING, TaskStatus.RUNNING) is False
        with pytest.raises(InvalidStateTransitionError) as exc_info:
            validate_task_transition(TaskStatus.PENDING, TaskStatus.RUNNING)
        assert "Invalid Task state transition" in str(exc_info.value)

    def test_illegal_jump_to_succeeded(self):
        """PENDING cannot jump straight to SUCCEEDED."""
        assert can_transition_task(TaskStatus.PENDING, TaskStatus.SUCCEEDED) is False
        with pytest.raises(InvalidStateTransitionError):
            validate_task_transition(TaskStatus.PENDING, TaskStatus.SUCCEEDED)

    def test_awaiting_approval_cannot_jump_to_succeeded(self):
        """AWAITING_APPROVAL cannot jump straight to SUCCEEDED without running."""
        assert can_transition_task(TaskStatus.AWAITING_APPROVAL, TaskStatus.SUCCEEDED) is False
        with pytest.raises(InvalidStateTransitionError):
            validate_task_transition(TaskStatus.AWAITING_APPROVAL, TaskStatus.SUCCEEDED)


class TestStepStateMachine:

    def test_valid_step_lifecycle(self):
        """PENDING -> RUNNING -> SUCCEEDED."""
        assert can_transition_step(StepStatus.PENDING, StepStatus.RUNNING) is True
        assert can_transition_step(StepStatus.RUNNING, StepStatus.SUCCEEDED) is True

    def test_step_failure(self):
        """RUNNING -> FAILED."""
        assert can_transition_step(StepStatus.RUNNING, StepStatus.FAILED) is True

    def test_step_skip(self):
        """PENDING -> SKIPPED."""
        assert can_transition_step(StepStatus.PENDING, StepStatus.SKIPPED) is True

    def test_illegal_step_jump(self):
        """PENDING cannot jump directly to SUCCEEDED without running."""
        assert can_transition_step(StepStatus.PENDING, StepStatus.SUCCEEDED) is False
        with pytest.raises(InvalidStateTransitionError):
            validate_step_transition(StepStatus.PENDING, StepStatus.SUCCEEDED)
