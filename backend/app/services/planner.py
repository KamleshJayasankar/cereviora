"""
CEREVIORA — Modular Task Planner & Policy Validator

This module implements the AI-ready planning architecture:
1. `BasePlanner`: Abstract interface decoupling planning from specific AI providers.
2. `DeterministicPlanner`: Zero-dependency, reliable, rule-based planner that works
   offline without API keys or external models.
3. `PlanPolicyValidator`: Strict policy and schema validation ensuring any generated
   plan (whether from deterministic logic or future LLMs like Ollama) conforms to
   safety bounds before execution.

Step Type Allowlist:
  - 'interpret' : Analyze natural language intent and parameters
  - 'research'  : Gather background knowledge or context
  - 'generate'  : Synthesize structured response or artifact
  - 'extract'   : Extract specific actionable checklist items
  - 'save'      : Persist results in application storage
  - 'verify'    : Confirm actual database/storage state matches expectation
  - 'general'   : General safe computation
"""

from abc import ABC, abstractmethod
from typing import Optional
import re
from app.schemas.task import TaskStepCreate


ALLOWED_STEP_TYPES = {
    "interpret",
    "research",
    "generate",
    "extract",
    "save",
    "verify",
    "general",
}


class PlanPolicyError(ValueError):
    """Raised when a generated plan violates safety policies or schema rules."""
    pass


class BasePlanner(ABC):
    """
    Abstract interface for all task planners.
    Enables swapping between DeterministicPlanner, OllamaPlanner, or Cloud LLMs
    without changing execution or database code.
    """

    @abstractmethod
    def plan(
        self,
        title: str,
        description: str = "",
        custom_instructions: Optional[str] = None,
    ) -> list[TaskStepCreate]:
        """Convert a task title and description into an ordered list of TaskStepCreate objects."""
        pass


class PlanPolicyValidator:
    """
    Validates generated plans against strict safety constraints.
    Treats all planner output (especially AI-generated plans) as untrusted input.
    """

    MIN_STEPS = 1
    MAX_STEPS = 15

    @classmethod
    def validate(cls, steps: list[TaskStepCreate]) -> list[TaskStepCreate]:
        if not steps:
            raise PlanPolicyError("Generated plan must contain at least one step.")

        if len(steps) > cls.MAX_STEPS:
            raise PlanPolicyError(
                f"Generated plan contains {len(steps)} steps, exceeding maximum of {cls.MAX_STEPS}."
            )

        # Verify step numbering is contiguous and 1-indexed
        for expected_num, step in enumerate(steps, start=1):
            if step.step_number != expected_num:
                raise PlanPolicyError(
                    f"Invalid step order: expected step {expected_num}, but found step {step.step_number}."
                )

            if not step.title or not step.title.strip():
                raise PlanPolicyError(f"Step {expected_num} has an empty title.")

            if len(step.title) > 200:
                raise PlanPolicyError(f"Step {expected_num} title exceeds 200 characters.")

            if step.step_type not in ALLOWED_STEP_TYPES:
                raise PlanPolicyError(
                    f"Step {expected_num} has disallowed step_type '{step.step_type}'. "
                    f"Allowed types: {sorted(ALLOWED_STEP_TYPES)}"
                )

            # Security sanity check: reject shell injection or script markers in step descriptions
            dangerous_patterns = [r"<script.*?>", r";\s*rm\s+-rf", r";\s*cat\s+/etc/passwd", r"\beval\(", r"\bexec\("]
            combined_text = f"{step.title} {step.description}"
            for pattern in dangerous_patterns:
                if re.search(pattern, combined_text, re.IGNORECASE):
                    raise PlanPolicyError(
                        f"Step {expected_num} contains potentially hazardous code pattern matching '{pattern}'."
                    )

        return steps


class DeterministicPlanner(BasePlanner):
    """
    Deterministic rule-based planner.
    Analyzes task intent using keyword heuristics and returns a calibrated,
    5-step structured execution plan including verification.
    """

    def plan(
        self,
        title: str,
        description: str = "",
        custom_instructions: Optional[str] = None,
    ) -> list[TaskStepCreate]:
        text = f"{title} {description} {custom_instructions or ''}".lower()

        if any(k in text for k in ["study", "learn", "course", "exam", "reading", "textbook"]):
            raw_steps = self._plan_study(title, description)
        elif any(k in text for k in ["research", "investigate", "explore", "survey", "benchmark"]):
            raw_steps = self._plan_research(title, description)
        elif any(k in text for k in ["code", "build", "develop", "bug", "refactor", "api"]):
            raw_steps = self._plan_development(title, description)
        elif any(k in text for k in ["report", "summary", "document", "notes", "write"]):
            raw_steps = self._plan_documentation(title, description)
        else:
            raw_steps = self._plan_general(title, description)

        # Always validate the generated plan against policy before returning
        return PlanPolicyValidator.validate(raw_steps)

    def _plan_study(self, title: str, description: str) -> list[TaskStepCreate]:
        return [
            TaskStepCreate(
                step_number=1,
                title="Interpret study scope & goals",
                description=f"Analyze target subject from '{title}' and define core mastery objectives.",
                step_type="interpret",
            ),
            TaskStepCreate(
                step_number=2,
                title="Synthesize structured curriculum outline",
                description="Decompose topics into sequential modules with allocated timelines.",
                step_type="generate",
            ),
            TaskStepCreate(
                step_number=3,
                title="Extract actionable milestones & checkpoints",
                description="Create concrete practice exercises, flashcards, and review checkpoints.",
                step_type="extract",
            ),
            TaskStepCreate(
                step_number=4,
                title="Save study plan to knowledge store",
                description="Persist structured study schedule and resources in application database.",
                step_type="save",
            ),
            TaskStepCreate(
                step_number=5,
                title="Verify plan completeness & persistence",
                description="Verify that the study plan and action items were stored and are retrievable.",
                step_type="verify",
            ),
        ]

    def _plan_research(self, title: str, description: str) -> list[TaskStepCreate]:
        return [
            TaskStepCreate(
                step_number=1,
                title="Interpret research query & constraints",
                description=f"Scope research inquiry for '{title}' and identify primary questions.",
                step_type="interpret",
            ),
            TaskStepCreate(
                step_number=2,
                title="Gather domain evidence & findings",
                description="Compile key data points, citations, and comparative insights.",
                step_type="research",
            ),
            TaskStepCreate(
                step_number=3,
                title="Synthesize conclusions & key takeaways",
                description="Extract structured summary and critical observations.",
                step_type="extract",
            ),
            TaskStepCreate(
                step_number=4,
                title="Save research digest to database",
                description="Store finalized findings and reference links in local knowledge store.",
                step_type="save",
            ),
            TaskStepCreate(
                step_number=5,
                title="Verify research record integrity",
                description="Confirm record existence in database and validate structural completeness.",
                step_type="verify",
            ),
        ]

    def _plan_development(self, title: str, description: str) -> list[TaskStepCreate]:
        return [
            TaskStepCreate(
                step_number=1,
                title="Interpret technical requirements & scope",
                description=f"Analyze software task '{title}' and define acceptance criteria.",
                step_type="interpret",
            ),
            TaskStepCreate(
                step_number=2,
                title="Generate implementation specification",
                description="Define data models, component interfaces, and architectural steps.",
                step_type="generate",
            ),
            TaskStepCreate(
                step_number=3,
                title="Extract test cases & validation checklist",
                description="Define unit test scenarios and verification criteria.",
                step_type="extract",
            ),
            TaskStepCreate(
                step_number=4,
                title="Save implementation plan to store",
                description="Persist developer specifications and milestones.",
                step_type="save",
            ),
            TaskStepCreate(
                step_number=5,
                title="Verify plan records in database",
                description="Validate that technical task steps are properly recorded.",
                step_type="verify",
            ),
        ]

    def _plan_documentation(self, title: str, description: str) -> list[TaskStepCreate]:
        return [
            TaskStepCreate(
                step_number=1,
                title="Interpret documentation audience & objectives",
                description=f"Analyze target topic '{title}' and intended readership.",
                step_type="interpret",
            ),
            TaskStepCreate(
                step_number=2,
                title="Draft structured document sections",
                description="Synthesize key sections, summaries, and instructional content.",
                step_type="generate",
            ),
            TaskStepCreate(
                step_number=3,
                title="Extract key highlights & action items",
                description="Condense executive summary and immediate next steps.",
                step_type="extract",
            ),
            TaskStepCreate(
                step_number=4,
                title="Save document artifact to database",
                description="Store completed document text in persistent storage.",
                step_type="save",
            ),
            TaskStepCreate(
                step_number=5,
                title="Verify document persistence & formatting",
                description="Verify storage consistency and accessibility.",
                step_type="verify",
            ),
        ]

    def _plan_general(self, title: str, description: str) -> list[TaskStepCreate]:
        return [
            TaskStepCreate(
                step_number=1,
                title="Interpret task requirements & context",
                description=f"Parse request '{title}' into structured input parameters.",
                step_type="interpret",
            ),
            TaskStepCreate(
                step_number=2,
                title="Synthesize execution strategy",
                description="Generate structured approach and workflow milestones.",
                step_type="generate",
            ),
            TaskStepCreate(
                step_number=3,
                title="Extract actionable checklist",
                description="Identify discrete checkpoints and deliverables.",
                step_type="extract",
            ),
            TaskStepCreate(
                step_number=4,
                title="Save plan details to database",
                description="Store structured operations and tracking records.",
                step_type="save",
            ),
            TaskStepCreate(
                step_number=5,
                title="Verify plan integrity & state",
                description="Confirm all steps are persisted and ready for approval.",
                step_type="verify",
            ),
        ]


# Factory helper
def get_planner() -> BasePlanner:
    """Return the configured planner instance (default: DeterministicPlanner)."""
    return DeterministicPlanner()
