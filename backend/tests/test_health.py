"""
CEREVIORA — Tests: Health Endpoint

We use pytest + httpx TestClient to make real HTTP requests against
the FastAPI application without needing a running server.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_returns_200():
    """The health endpoint must return HTTP 200."""
    response = client.get("/health")
    assert response.status_code == 200


def test_health_response_shape():
    """The health endpoint must return the expected JSON keys."""
    response = client.get("/health")
    body = response.json()
    assert body["status"] == "ok"
    assert "app" in body
    assert "version" in body
    assert "timestamp" in body


def test_root_returns_200():
    """The root path must return 200 with a welcome message."""
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()
