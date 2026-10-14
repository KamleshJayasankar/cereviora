"""
CEREVIORA — Tests: Task CRUD API

These tests cover every important behaviour of the task endpoints:
- Creating tasks (valid and invalid inputs)
- Listing tasks (empty and populated)
- Retrieving a single task
- Updating tasks (partial updates)
- Deleting tasks
- Correct 404 responses for missing IDs
- Dashboard counts endpoint
- Persistence: data survives within a session

All tests use the `client` fixture from conftest.py which routes
requests to an in-memory SQLite database — no real data is touched.
"""

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Helper: create a task and return its JSON body
# ─────────────────────────────────────────────────────────────────────────────

def make_task(client, title="Test Task", description="A test description"):
    """POST /tasks and return the response body dict."""
    r = client.post("/tasks", json={"title": title, "description": description})
    assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
    return r.json()


# ─────────────────────────────────────────────────────────────────────────────
# POST /tasks — Create
# ─────────────────────────────────────────────────────────────────────────────

class TestCreateTask:

    def test_create_returns_201(self, client):
        """Creating a valid task must return HTTP 201 Created."""
        r = client.post("/tasks", json={"title": "My First Task"})
        assert r.status_code == 201

    def test_create_returns_expected_fields(self, client):
        """The response must include id, title, description, status, timestamps."""
        r = client.post("/tasks", json={"title": "Study Python", "description": "Focus on SQLAlchemy"})
        body = r.json()
        assert body["title"] == "Study Python"
        assert body["description"] == "Focus on SQLAlchemy"
        assert body["status"] == "PENDING"    # new tasks start as PENDING
        assert "id" in body                   # auto-generated UUID
        assert "created_at" in body
        assert "updated_at" in body
        assert body["steps"] == []            # no steps yet (Day 3)

    def test_create_trims_whitespace_from_title(self, client):
        """Leading/trailing whitespace should be stripped from the title."""
        r = client.post("/tasks", json={"title": "  Trimmed Title  "})
        assert r.json()["title"] == "Trimmed Title"

    def test_create_with_no_description_defaults_to_empty_string(self, client):
        """Description is optional; it defaults to an empty string."""
        r = client.post("/tasks", json={"title": "No Desc"})
        assert r.json()["description"] == ""

    def test_create_missing_title_returns_422(self, client):
        """
        422 Unprocessable Entity — the request was well-formed JSON
        but failed validation (title is required).
        """
        r = client.post("/tasks", json={"description": "No title provided"})
        assert r.status_code == 422

    def test_create_blank_title_returns_422(self, client):
        """A title that is only whitespace must be rejected."""
        r = client.post("/tasks", json={"title": "   "})
        assert r.status_code == 422

    def test_create_title_too_long_returns_422(self, client):
        """Titles over 200 characters must be rejected."""
        r = client.post("/tasks", json={"title": "x" * 201})
        assert r.status_code == 422

    def test_create_empty_body_returns_422(self, client):
        """An empty JSON body must be rejected."""
        r = client.post("/tasks", json={})
        assert r.status_code == 422

    def test_create_generates_unique_ids(self, client):
        """Two tasks created separately must have different IDs."""
        id1 = make_task(client, "Task A")["id"]
        id2 = make_task(client, "Task B")["id"]
        assert id1 != id2


# ─────────────────────────────────────────────────────────────────────────────
# GET /tasks — List
# ─────────────────────────────────────────────────────────────────────────────

class TestListTasks:

    def test_empty_list(self, client):
        """No tasks yet → response has empty list and total=0."""
        r = client.get("/tasks")
        assert r.status_code == 200
        body = r.json()
        assert body["tasks"] == []
        assert body["total"] == 0
        assert body["has_more"] is False

    def test_lists_created_tasks(self, client):
        """Tasks that were created should appear in the list."""
        make_task(client, "Alpha")
        make_task(client, "Beta")
        r = client.get("/tasks")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 2
        titles = [t["title"] for t in body["tasks"]]
        assert "Alpha" in titles
        assert "Beta" in titles

    def test_newest_first_ordering(self, client):
        """Tasks are returned newest-first."""
        make_task(client, "First")
        make_task(client, "Second")
        tasks = client.get("/tasks").json()["tasks"]
        assert tasks[0]["title"] == "Second"
        assert tasks[1]["title"] == "First"

    def test_filter_by_status(self, client):
        """?status=PENDING should return only PENDING tasks."""
        make_task(client, "Pending Task")
        r = client.get("/tasks?status=PENDING")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["tasks"][0]["status"] == "PENDING"

    def test_filter_returns_empty_for_nonmatching_status(self, client):
        """Filtering by SUCCEEDED when all tasks are PENDING returns empty list."""
        make_task(client, "Some task")
        r = client.get("/tasks?status=SUCCEEDED")
        assert r.json()["total"] == 0

    def test_invalid_status_filter_returns_422(self, client):
        """An unrecognised status value must be rejected with 422."""
        r = client.get("/tasks?status=INVALID_STATUS")
        assert r.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# GET /tasks/{task_id} — Retrieve single
# ─────────────────────────────────────────────────────────────────────────────

class TestGetTask:

    def test_get_existing_task(self, client):
        """Retrieve a task by its ID."""
        created = make_task(client, "Retrievable")
        r = client.get(f"/tasks/{created['id']}")
        assert r.status_code == 200
        assert r.json()["id"] == created["id"]
        assert r.json()["title"] == "Retrievable"

    def test_get_nonexistent_task_returns_404(self, client):
        """A UUID that doesn't exist in the DB must return 404."""
        r = client.get("/tasks/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404

    def test_404_error_has_detail_field(self, client):
        """FastAPI 404 errors must include a 'detail' field explaining what happened."""
        r = client.get("/tasks/nonexistent-id")
        assert "detail" in r.json()


# ─────────────────────────────────────────────────────────────────────────────
# PATCH /tasks/{task_id} — Update
# ─────────────────────────────────────────────────────────────────────────────

class TestUpdateTask:

    def test_update_title(self, client):
        """PATCH with a new title must update only the title."""
        task = make_task(client, "Original Title", "Original Desc")
        r = client.patch(f"/tasks/{task['id']}", json={"title": "Updated Title"})
        assert r.status_code == 200
        updated = r.json()
        assert updated["title"] == "Updated Title"
        assert updated["description"] == "Original Desc"   # unchanged

    def test_update_description(self, client):
        """PATCH with a new description must update only the description."""
        task = make_task(client, "Stable Title", "Old Desc")
        r = client.patch(f"/tasks/{task['id']}", json={"description": "New Desc"})
        assert r.status_code == 200
        updated = r.json()
        assert updated["title"] == "Stable Title"          # unchanged
        assert updated["description"] == "New Desc"

    def test_update_both_fields(self, client):
        """PATCH can update title and description together."""
        task = make_task(client)
        r = client.patch(f"/tasks/{task['id']}", json={"title": "T2", "description": "D2"})
        assert r.status_code == 200
        assert r.json()["title"] == "T2"
        assert r.json()["description"] == "D2"

    def test_empty_patch_returns_task_unchanged(self, client):
        """An empty PATCH body must not error — task is returned as-is."""
        task = make_task(client, "Keep Me")
        r = client.patch(f"/tasks/{task['id']}", json={})
        assert r.status_code == 200
        assert r.json()["title"] == "Keep Me"

    def test_update_nonexistent_task_returns_404(self, client):
        """Patching a task that doesn't exist must return 404."""
        r = client.patch("/tasks/00000000-0000-0000-0000-000000000000", json={"title": "X"})
        assert r.status_code == 404

    def test_update_blank_title_returns_422(self, client):
        """PATCH with a blank title must be rejected."""
        task = make_task(client)
        r = client.patch(f"/tasks/{task['id']}", json={"title": "   "})
        assert r.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# DELETE /tasks/{task_id} — Delete
# ─────────────────────────────────────────────────────────────────────────────

class TestDeleteTask:

    def test_delete_existing_task(self, client):
        """DELETE a task returns 200 with a confirmation message."""
        task = make_task(client, "To Be Deleted")
        r = client.delete(f"/tasks/{task['id']}")
        assert r.status_code == 200
        assert "message" in r.json()

    def test_deleted_task_is_gone(self, client):
        """After deletion, GET /tasks/{id} must return 404."""
        task = make_task(client)
        client.delete(f"/tasks/{task['id']}")
        r = client.get(f"/tasks/{task['id']}")
        assert r.status_code == 404

    def test_deleted_task_removed_from_list(self, client):
        """After deletion, the task no longer appears in GET /tasks."""
        task = make_task(client)
        client.delete(f"/tasks/{task['id']}")
        body = client.get("/tasks").json()
        ids = [t["id"] for t in body["tasks"]]
        assert task["id"] not in ids

    def test_delete_nonexistent_task_returns_404(self, client):
        """Deleting a task that doesn't exist must return 404."""
        r = client.delete("/tasks/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404

    def test_double_delete_returns_404(self, client):
        """Deleting the same task twice: first 200, second 404."""
        task = make_task(client)
        r1 = client.delete(f"/tasks/{task['id']}")
        r2 = client.delete(f"/tasks/{task['id']}")
        assert r1.status_code == 200
        assert r2.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# GET /tasks/counts — Dashboard stats
# ─────────────────────────────────────────────────────────────────────────────

class TestTaskCounts:

    def test_counts_returns_all_statuses(self, client):
        """Counts endpoint must have a key for every known status."""
        r = client.get("/tasks/counts")
        assert r.status_code == 200
        body = r.json()
        for status in ["PENDING", "AWAITING_APPROVAL", "RUNNING", "SUCCEEDED", "FAILED", "total"]:
            assert status in body, f"Missing key: {status}"

    def test_counts_zero_when_no_tasks(self, client):
        """All counts must be 0 before any tasks are created."""
        body = client.get("/tasks/counts").json()
        assert body["total"] == 0
        assert body["PENDING"] == 0

    def test_counts_reflect_created_tasks(self, client):
        """Creating tasks must increment PENDING and total counts."""
        make_task(client, "A")
        make_task(client, "B")
        body = client.get("/tasks/counts").json()
        assert body["PENDING"] == 2
        assert body["total"] == 2

    def test_counts_update_after_deletion(self, client):
        """Deleting a task must decrement the count."""
        task = make_task(client)
        assert client.get("/tasks/counts").json()["total"] == 1
        client.delete(f"/tasks/{task['id']}")
        assert client.get("/tasks/counts").json()["total"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# Persistence within a session
# ─────────────────────────────────────────────────────────────────────────────

class TestPersistence:

    def test_task_survives_subsequent_reads(self, client):
        """A created task should be retrievable in multiple subsequent GET calls."""
        task = make_task(client, "Persistent Task")
        for _ in range(3):
            r = client.get(f"/tasks/{task['id']}")
            assert r.status_code == 200
            assert r.json()["title"] == "Persistent Task"

    def test_updated_title_persists(self, client):
        """Updated title must appear in subsequent GET calls."""
        task = make_task(client, "Before")
        client.patch(f"/tasks/{task['id']}", json={"title": "After"})
        r = client.get(f"/tasks/{task['id']}")
        assert r.json()["title"] == "After"
