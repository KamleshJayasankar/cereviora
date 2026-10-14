"""Day 4: approval gates, fixed execution handlers, verification, and audit history."""
from app.services import execution_engine, task_service


def planned(client, title="Study safe execution"):
    task = client.post("/tasks", json={"title": title}).json()
    return client.post(f"/tasks/{task['id']}/plan").json()


def test_execution_requires_approval(client):
    task = planned(client)
    response = client.post(f"/tasks/{task['id']}/execute")
    assert response.status_code == 403
    assert client.get(f"/tasks/{task['id']}/history").json() == []


def test_approved_task_executes_and_verifies_database_state(client):
    task = planned(client)
    task_id = task["id"]
    approved = client.post(f"/tasks/{task_id}/approve")
    assert approved.status_code == 200
    assert approved.json()["approved_at"]
    result = client.post(f"/tasks/{task_id}/execute")
    assert result.status_code == 200
    assert result.json()["status"] == "SUCCEEDED"
    assert all(step["status"] == "SUCCEEDED" for step in result.json()["steps"])
    history = client.get(f"/tasks/{task_id}/history").json()
    assert history[0]["event_type"] == "APPROVAL"
    assert len([item for item in history if item["event_type"] == "STEP"]) == 5
    step_history = [item for item in history if item["event_type"] == "STEP"]
    assert step_history[-1]["verified"] is True
    assert step_history[-2]["verified"] is True  # save operation was verified by its database write
    assert all(item["verified"] is False for item in step_history[:-2])


def test_failed_execution_is_audited_and_can_be_replanned_for_retry(client, monkeypatch):
    task = planned(client)
    task_id = task["id"]
    client.post(f"/tasks/{task_id}/approve")
    original = execution_engine.execute_step
    failed_once = {"value": False}

    def fail_first_step(db, current_task, step):
        if not failed_once["value"]:
            failed_once["value"] = True
            raise RuntimeError("simulated operation failure")
        return original(db, current_task, step)

    monkeypatch.setattr(task_service, "execute_step", fail_first_step)
    first = client.post(f"/tasks/{task_id}/execute")
    assert first.json()["status"] == "FAILED"
    assert first.json()["steps"][0]["error_message"] == "simulated operation failure"
    assert any(entry["error_details"] == "simulated operation failure" for entry in client.get(f"/tasks/{task_id}/history").json())

    assert client.post(f"/tasks/{task_id}/execute").status_code == 400
    assert client.post(f"/tasks/{task_id}/plan").status_code == 200
    assert client.post(f"/tasks/{task_id}/approve").status_code == 200
    retried = client.post(f"/tasks/{task_id}/execute")
    assert retried.json()["status"] == "SUCCEEDED"


def test_verification_failure_fails_task_and_is_recorded(client, monkeypatch):
    task = planned(client)
    task_id = task["id"]
    client.post(f"/tasks/{task_id}/approve")
    original = execution_engine.execute_step

    def fail_verification(db, current_task, step):
        if step.step_type == "verify":
            raise execution_engine.ExecutionPolicyError("database verification mismatch")
        return original(db, current_task, step)

    monkeypatch.setattr(task_service, "execute_step", fail_verification)
    result = client.post(f"/tasks/{task_id}/execute")
    assert result.json()["status"] == "FAILED"
    history = client.get(f"/tasks/{task_id}/history").json()
    verification = [entry for entry in history if entry["step_id"] and entry["error_details"]]
    assert verification[-1]["error_details"] == "database verification mismatch"
    assert verification[-1]["verified"] is False


def test_approval_and_execution_reject_invalid_or_repeated_transitions(client):
    task = client.post("/tasks", json={"title": "Unplanned"}).json()
    assert client.post(f"/tasks/{task['id']}/approve").status_code == 400
    planned_task = planned(client)
    task_id = planned_task["id"]
    assert client.post(f"/tasks/{task_id}/approve").status_code == 200
    assert client.post(f"/tasks/{task_id}/approve").status_code == 409
    assert client.post(f"/tasks/{task_id}/execute").json()["status"] == "SUCCEEDED"
    assert client.post(f"/tasks/{task_id}/execute").status_code == 400
