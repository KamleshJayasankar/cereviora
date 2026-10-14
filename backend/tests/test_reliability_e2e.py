"""
CEREVIORA Day 6 — End-to-End Workflow Verification and Reliability Test Suite

This test module systematically tests:
1. Complete workflow: Create -> Plan -> Awaiting Approval -> Approve -> Execute -> Artifact Persistence -> Verification -> History.
2. Direct SQLite database state inspection (tables: tasks, task_steps, execution_records, task_artifacts).
3. Failure handling and safety gates:
   - Execution without approval rejected (403).
   - Repeated approval rejected (409).
   - Invalid state transitions rejected (400).
   - Simulated execution and verification failures properly audited.
   - Retrying failed tasks does not corrupt database state.
   - Task edit invalidates prior approval.
   - Error response format conforms to frontend contract ({"detail": "..."}).
"""

import pytest
from app.models.task import Task, TaskStatus
from app.models.task_step import TaskStep, StepStatus
from app.models.execution_record import ExecutionRecord
from app.models.task_artifact import TaskArtifact
from app.services import execution_engine, task_service


class TestEndToEndWorkflow:
    """Phase 2: Comprehensive verification of the complete task lifecycle."""

    def test_complete_e2e_lifecycle_and_sqlite_persistence(self, client, db_session):
        # 1. Create a task through API (contract used by React frontend)
        create_resp = client.post(
            "/tasks",
            json={
                "title": "E2E Architecture Research",
                "description": "Analyze distributed consensus protocols and summarize findings.",
            },
        )
        assert create_resp.status_code == 201
        task_data = create_resp.json()
        task_id = task_data["id"]

        assert task_data["title"] == "E2E Architecture Research"
        assert task_data["status"] == "PENDING"
        assert task_data["approved_at"] is None
        assert task_data["steps"] == []

        # 2. Generate structured execution plan
        plan_resp = client.post(f"/tasks/{task_id}/plan")
        assert plan_resp.status_code == 200
        plan_data = plan_resp.json()

        # 3. Verify task enters AWAITING_APPROVAL and contains valid steps
        assert plan_data["status"] == "AWAITING_APPROVAL"
        assert plan_data["approved_at"] is None
        assert len(plan_data["steps"]) >= 5
        assert all(step["status"] == "PENDING" for step in plan_data["steps"])

        # Check step types contain the expected pipeline
        step_types = [step["step_type"] for step in plan_data["steps"]]
        assert "interpret" in step_types
        assert "save" in step_types
        assert "verify" in step_types

        # Pre-approval execution attempt MUST fail (Phase 3 requirement)
        premature_exec = client.post(f"/tasks/{task_id}/execute")
        assert premature_exec.status_code == 403
        assert "approval is required" in premature_exec.json()["detail"].lower()

        # 4. Approve the plan
        approve_resp = client.post(f"/tasks/{task_id}/approve")
        assert approve_resp.status_code == 200
        approved_data = approve_resp.json()
        assert approved_data["status"] == "AWAITING_APPROVAL"
        assert approved_data["approved_at"] is not None

        # Verify initial approval audit record exists in database
        initial_history = client.get(f"/tasks/{task_id}/history").json()
        assert len(initial_history) == 1
        assert initial_history[0]["event_type"] == "APPROVAL"
        assert initial_history[0]["status"] == "APPROVED"
        assert initial_history[0]["verified"] is True

        # 5. Execute the approved plan
        exec_resp = client.post(f"/tasks/{task_id}/execute")
        assert exec_resp.status_code == 200
        exec_data = exec_resp.json()
        assert exec_data["status"] == "SUCCEEDED"
        assert all(step["status"] == "SUCCEEDED" for step in exec_data["steps"])

        # 6 & 7. Confirm output artifact is persisted directly in SQLite database
        artifacts = db_session.query(TaskArtifact).filter(TaskArtifact.task_id == task_id).all()
        assert len(artifacts) == 1
        artifact = artifacts[0]
        assert "Task plan: E2E Architecture Research" in artifact.content
        assert artifact.created_at is not None

        # Verify task row in SQLite database directly
        db_task = db_session.query(Task).filter(Task.id == task_id).one()
        assert db_task.status == TaskStatus.SUCCEEDED
        assert db_task.approved_at is not None

        # Verify all step rows in SQLite database directly
        db_steps = db_session.query(TaskStep).filter(TaskStep.task_id == task_id).order_by(TaskStep.step_number).all()
        assert len(db_steps) == len(plan_data["steps"])
        for step in db_steps:
            assert step.status == StepStatus.SUCCEEDED
            assert step.completed_at is not None
            assert step.result_summary is not None

        # 8. Inspect persistent audit records in SQLite
        history_records = db_session.query(ExecutionRecord).filter(ExecutionRecord.task_id == task_id).order_by(ExecutionRecord.created_at, ExecutionRecord.id).all()
        # 1 APPROVAL + N STEP records
        assert len(history_records) == 1 + len(db_steps)
        assert history_records[0].event_type == "APPROVAL"
        assert history_records[0].status == "APPROVED"

        step_records = [r for r in history_records if r.event_type == "STEP"]
        assert all(r.status == "SUCCEEDED" for r in step_records)

        # The save step and verify step records have verified=True
        save_record = next(r for r in step_records if "save" in (r.input_summary or "").lower())
        verify_record = next(r for r in step_records if "verify" in (r.input_summary or "").lower())
        assert save_record.verified is True
        assert verify_record.verified is True
        assert "database" in verify_record.verification_result.lower()

        # 9. Verify task counts endpoint used by Dashboard Command Center
        counts_resp = client.get("/tasks/counts")
        assert counts_resp.status_code == 200
        counts = counts_resp.json()
        assert counts["total"] == 1
        assert counts["SUCCEEDED"] == 1
        assert counts["RUNNING"] == 0
        assert counts["AWAITING_APPROVAL"] == 0
        assert counts["FAILED"] == 0
        assert counts["PENDING"] == 0


class TestFailureHandlingAndSafetyGates:
    """Phase 3: Verify failure handling, guardrails, and reliability under errors."""

    def test_unapproved_execution_rejected_with_403(self, client):
        """Execution without human approval is rejected."""
        task = client.post("/tasks", json={"title": "Unapproved task"}).json()
        client.post(f"/tasks/{task['id']}/plan")

        resp = client.post(f"/tasks/{task['id']}/execute")
        assert resp.status_code == 403
        assert resp.json() == {"detail": "Task approval is required before execution."}

    def test_repeated_approval_rejected_with_409(self, client):
        """Cannot approve an already-approved task plan."""
        task = client.post("/tasks", json={"title": "Double approval test"}).json()
        client.post(f"/tasks/{task['id']}/plan")

        app1 = client.post(f"/tasks/{task['id']}/approve")
        assert app1.status_code == 200

        app2 = client.post(f"/tasks/{task['id']}/approve")
        assert app2.status_code == 409
        assert "already been approved" in app2.json()["detail"].lower()

    def test_invalid_state_transitions_rejected_with_400(self, client):
        """State machine rejects illegal transition attempts."""
        # Task in PENDING cannot be approved or executed
        task = client.post("/tasks", json={"title": "Pending task"}).json()

        exec_pending = client.post(f"/tasks/{task['id']}/execute")
        assert exec_pending.status_code == 400

        approve_pending = client.post(f"/tasks/{task['id']}/approve")
        assert approve_pending.status_code == 400

    def test_task_edit_invalidates_prior_approval(self, client):
        """Editing task title or description removes approval timestamp."""
        task = client.post("/tasks", json={"title": "Original Title"}).json()
        task_id = task["id"]
        client.post(f"/tasks/{task_id}/plan")
        client.post(f"/tasks/{task_id}/approve")

        # Verify task is approved
        approved_task = client.get(f"/tasks/{task_id}").json()
        assert approved_task["approved_at"] is not None

        # Edit task
        client.patch(f"/tasks/{task_id}", json={"title": "Modified Title"})

        # Verify approval is now wiped
        modified_task = client.get(f"/tasks/{task_id}").json()
        assert modified_task["title"] == "Modified Title"
        assert modified_task["approved_at"] is None

        # Execution must now be blocked
        blocked = client.post(f"/tasks/{task_id}/execute")
        assert blocked.status_code == 403

    def test_execution_failure_is_audited_and_retry_cleans_slate(self, client, db_session, monkeypatch):
        """Simulate execution failure: audits failure, marks task FAILED, and allows clean replanning & retry."""
        task = client.post("/tasks", json={"title": "Failure and Retry Task"}).json()
        task_id = task["id"]
        client.post(f"/tasks/{task_id}/plan")
        client.post(f"/tasks/{task_id}/approve")

        original_execute_step = execution_engine.execute_step

        # Step fails on generate
        def faulty_execute_step(db, current_task, step):
            if step.step_type == "generate":
                raise RuntimeError("Service timeout during generation")
            return original_execute_step(db, current_task, step)

        monkeypatch.setattr(task_service, "execute_step", faulty_execute_step)

        # Execute -> should fail
        fail_resp = client.post(f"/tasks/{task_id}/execute")
        assert fail_resp.status_code == 200
        fail_data = fail_resp.json()
        assert fail_data["status"] == "FAILED"

        # Check DB state
        db_task = db_session.query(Task).filter(Task.id == task_id).one()
        assert db_task.status == TaskStatus.FAILED

        # Check audit trail recorded the failure
        history = client.get(f"/tasks/{task_id}/history").json()
        failed_records = [r for r in history if r["status"] == "FAILED"]
        assert len(failed_records) == 1
        assert "Service timeout during generation" in failed_records[0]["error_details"]
        assert failed_records[0]["verified"] is False

        # Verify that no task artifact was saved prior to failure
        artifacts_before_retry = db_session.query(TaskArtifact).filter(TaskArtifact.task_id == task_id).count()
        assert artifacts_before_retry == 0

        # Now test clean retry: restore original execute_step
        monkeypatch.setattr(task_service, "execute_step", original_execute_step)

        # Cannot directly execute failed task without replanning & approving
        cannot_reexec = client.post(f"/tasks/{task_id}/execute")
        assert cannot_reexec.status_code == 400

        # Replan transitions FAILED -> PENDING -> AWAITING_APPROVAL cleanly
        replan_resp = client.post(f"/tasks/{task_id}/plan")
        assert replan_resp.status_code == 200
        assert replan_resp.json()["status"] == "AWAITING_APPROVAL"

        # Approve
        reapprove = client.post(f"/tasks/{task_id}/approve")
        assert reapprove.status_code == 200

        # Retry execution succeeds
        retry_exec = client.post(f"/tasks/{task_id}/execute")
        assert retry_exec.status_code == 200
        assert retry_exec.json()["status"] == "SUCCEEDED"

        # Confirm exactly 1 artifact in SQLite (no duplicate or corrupted artifacts)
        artifacts_after_retry = db_session.query(TaskArtifact).filter(TaskArtifact.task_id == task_id).all()
        assert len(artifacts_after_retry) == 1

    def test_database_verification_failure_halts_and_audits(self, client, db_session, monkeypatch):
        """Simulate verification failure: task fails and audit log marks verification as unverified."""
        task = client.post("/tasks", json={"title": "Verification Failure Test"}).json()
        task_id = task["id"]
        client.post(f"/tasks/{task_id}/plan")
        client.post(f"/tasks/{task_id}/approve")

        original_execute_step = execution_engine.execute_step

        def bad_verification(db, current_task, step):
            if step.step_type == "verify":
                raise execution_engine.ExecutionPolicyError("SQLite artifact hash mismatch")
            return original_execute_step(db, current_task, step)

        monkeypatch.setattr(task_service, "execute_step", bad_verification)

        fail_resp = client.post(f"/tasks/{task_id}/execute")
        assert fail_resp.status_code == 200
        assert fail_resp.json()["status"] == "FAILED"

        # Check audit trail recorded verification failure
        history = client.get(f"/tasks/{task_id}/history").json()
        verify_failed = [r for r in history if r["status"] == "FAILED"]
        assert len(verify_failed) >= 1
        assert "SQLite artifact hash mismatch" in verify_failed[-1]["error_details"]
        assert verify_failed[-1]["verified"] is False
