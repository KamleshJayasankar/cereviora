"""
CEREVIORA — Tests: Deterministic Planner & Policy Validator

Tests verify:
1. DeterministicPlanner generates tailored 5-step plans for different domain keywords.
2. Step types and ordering strictly conform to the execution contract.
3. PlanPolicyValidator rejects invalid step schemas, bad types, and out-of-order steps.
4. PlanPolicyValidator rejects malicious payloads or script tags.
"""

import pytest
from app.schemas.task import TaskStepCreate
from app.services.planner import (
    DeterministicPlanner,
    PlanPolicyValidator,
    PlanPolicyError,
    ALLOWED_STEP_TYPES,
)


class TestDeterministicPlanner:

    @pytest.fixture
    def planner(self):
        return DeterministicPlanner()

    def test_plan_study_task(self, planner):
        steps = planner.plan("Prepare study plan for Machine Learning", "Cover linear models and neural networks")
        assert len(steps) == 5
        assert [s.step_number for s in steps] == [1, 2, 3, 4, 5]
        assert steps[0].step_type == "interpret"
        assert steps[3].step_type == "save"
        assert steps[4].step_type == "verify"
        assert "study" in steps[0].title.lower() or "study" in steps[0].description.lower()

    def test_plan_research_task(self, planner):
        steps = planner.plan("Research vector databases", "Compare Qdrant, Milvus, and Pinecone")
        assert len(steps) == 5
        types = [s.step_type for s in steps]
        assert "research" in types
        assert "verify" in types

    def test_plan_development_task(self, planner):
        steps = planner.plan("Build REST API endpoints", "Add authentication and database models")
        assert len(steps) == 5
        assert any("technical" in s.title.lower() or "implementation" in s.title.lower() for s in steps)

    def test_plan_general_task(self, planner):
        steps = planner.plan("Organize quarterly goals", "Prepare team alignment roadmap")
        assert len(steps) == 5
        assert [s.step_number for s in steps] == [1, 2, 3, 4, 5]
        for step in steps:
            assert step.step_type in ALLOWED_STEP_TYPES


class TestPlanPolicyValidator:

    def test_valid_plan_passes(self):
        valid_steps = [
            TaskStepCreate(step_number=1, title="Step 1", step_type="interpret"),
            TaskStepCreate(step_number=2, title="Step 2", step_type="generate"),
            TaskStepCreate(step_number=3, title="Step 3", step_type="save"),
        ]
        result = PlanPolicyValidator.validate(valid_steps)
        assert len(result) == 3

    def test_empty_plan_fails(self):
        with pytest.raises(PlanPolicyError, match="must contain at least one step"):
            PlanPolicyValidator.validate([])

    def test_too_many_steps_fails(self):
        steps = [
            TaskStepCreate(step_number=i, title=f"Step {i}", step_type="general")
            for i in range(1, 20)
        ]
        with pytest.raises(PlanPolicyError, match="exceeding maximum"):
            PlanPolicyValidator.validate(steps)

    def test_non_contiguous_step_numbers_fails(self):
        steps = [
            TaskStepCreate(step_number=1, title="First", step_type="interpret"),
            TaskStepCreate(step_number=3, title="Skipped step 2", step_type="generate"),
        ]
        with pytest.raises(PlanPolicyError, match="Invalid step order"):
            PlanPolicyValidator.validate(steps)

    def test_disallowed_step_type_fails(self):
        steps = [
            TaskStepCreate(step_number=1, title="Step 1", step_type="unauthorized_exec_type"),
        ]
        with pytest.raises(PlanPolicyError, match="disallowed step_type"):
            PlanPolicyValidator.validate(steps)

    def test_dangerous_pattern_rejected(self):
        steps = [
            TaskStepCreate(
                step_number=1,
                title="Execute payload",
                description="test; rm -rf / ; echo done",
                step_type="general",
            ),
        ]
        with pytest.raises(PlanPolicyError, match="potentially hazardous code pattern"):
            PlanPolicyValidator.validate(steps)
