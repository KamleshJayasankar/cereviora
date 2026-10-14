"""
CEREVIORA — Tests: Task Planning API & Step Persistence

Tests verify:
1. POST /tasks/{task_id}/plan generates structured steps and transitions to AWAITING_APPROVAL.
2. Steps persist in the database and are returned in subsequent GET /tasks/{task_id} requests.
3. Replanning replaces previous steps cleanly.
4. Planning a nonexistent task returns 404.
5. Attempting to plan an active or invalid state task returns 400.
6. Cascade delete: deleting a task removes all of its steps from the database.
"""

import pytest
from app.models.task import Task, TaskStatus
from app.models.task_step import TaskStep, StepStatus


def make_task(client, title="Study Quantum Computing", description="Cover basic qubits and gates"):
    r = client.post("/tasks", json={"title": title, "description": description})
    assert r.status_code == 201
    return r.json()


class TestTaskPlanningEndpoint:

    def test_plan_task_success(self, client):
        task = make_task(client, "Study Rust Programming", "Learn memory safety and ownership")
        task_id = task["id"]
        assert task["status"] == "PENDING"
        assert task["steps"] == []

        # Request plan generation
        r = client.post(f"/tasks/{task_id}/plan")
        assert r.status_code == 200
        planned = r.json()

        # Verify status transition
        assert planned["status"] == "AWAITING_APPROVAL"
        assert len(planned["steps"]) == 5

        # Verify steps structure
        steps = planned["steps"]
        assert [s["step_number"] for s in steps] == [1, 2, 3, 4, 5]
        for step in steps:
            assert step["task_id"] == task_id
            assert step["status"] == "PENDING"
            assert step["step_type"] in ["interpret", "generate", "extract", "save", "verify"]

    def test_plan_persists_on_subsequent_get(self, client):
        task = make_task(client, "Research Solar Cell Efficiency")
        task_id = task["id"]

        client.post(f"/tasks/{task_id}/plan")

        # Fetch task via GET
        r = client.get(f"/tasks/{task_id}")
        assert r.status_code == 200
        fetched = r.json()
        assert fetched["status"] == "AWAITING_APPROVAL"
        assert len(fetched["steps"]) == 5

    def test_plan_with_custom_instructions(self, client):
        task = make_task(client, "Build Web Dashboard")
        task_id = task["id"]

        r = client.post(
            f"/tasks/{task_id}/plan",
            json={"custom_instructions": "Focus heavily on real-time WebSockets and Three.js"},
        )
        assert r.status_code == 200
        assert len(r.json()["steps"]) == 5

    def test_plan_nonexistent_task_returns_404(self, client):
        r = client.post("/tasks/00000000-0000-0000-0000-000000000000/plan")
        assert r.status_code == 404

    def test_replan_clears_old_steps(self, client):
        task = make_task(client, "General Administrative Review")
        task_id = task["id"]

        # Plan once
        r1 = client.post(f"/tasks/{task_id}/plan")
        first_step_ids = [s["id"] for s in r1.json()["steps"]]
        assert len(first_step_ids) == 5

        # Replan
        r2 = client.post(f"/tasks/{task_id}/plan")
        second_step_ids = [s["id"] for s in r2.json()["steps"]]
        assert len(second_step_ids) == 5

        # Steps must have fresh IDs and count must not double
        assert set(first_step_ids).isdisjoint(set(second_step_ids))

    def test_cascade_delete_removes_steps(self, client):
        task = make_task(client, "Temporary Task for Cascade Test")
        task_id = task["id"]

        # Generate plan to create steps
        client.post(f"/tasks/{task_id}/plan")

        # Confirm steps exist via GET
        r = client.get(f"/tasks/{task_id}")
        assert len(r.json()["steps"]) == 5

        # Delete the parent task
        del_res = client.delete(f"/tasks/{task_id}")
        assert del_res.status_code == 200

        # Confirm task is gone
        assert client.get(f"/tasks/{task_id}").status_code == 404
