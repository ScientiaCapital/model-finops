"""Tests for admin monitoring endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

ADMIN_KEY = "admin-key-for-tests-only-0123456789"
ADMIN_HEADERS = {"X-Admin-Key": ADMIN_KEY}


@pytest.fixture(autouse=True)
def admin_key(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", ADMIN_KEY)


def test_feedback_summary_endpoint(authenticated_client):
    """Test /admin/feedback/summary returns stats."""
    response = authenticated_client.get("/admin/feedback/summary", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    data = response.json()

    assert "total_feedback" in data
    assert "avg_quality_score" in data
    assert "models" in data
    assert isinstance(data["models"], list)


def test_learning_status_endpoint(authenticated_client):
    """Test /admin/learning/status returns status."""
    response = authenticated_client.get("/admin/learning/status", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    data = response.json()

    assert "last_retraining_run" in data
    assert "confidence_distribution" in data
    assert "high" in data["confidence_distribution"]
    assert "medium" in data["confidence_distribution"]
    assert "low" in data["confidence_distribution"]


def test_retrain_dry_run_endpoint(authenticated_client):
    """Test /admin/learning/retrain?dry_run=true."""
    response = authenticated_client.post(
        "/admin/learning/retrain?dry_run=true", headers=ADMIN_HEADERS
    )

    assert response.status_code == 200
    data = response.json()

    assert "changes" in data
    assert "total_changes" in data
    assert data["dry_run"] is True


def test_retrain_actual_endpoint(authenticated_client):
    """Test /admin/learning/retrain without dry_run."""
    response = authenticated_client.post(
        "/admin/learning/retrain?dry_run=false", headers=ADMIN_HEADERS
    )

    assert response.status_code == 200
    data = response.json()

    assert "run_id" in data
    assert data["dry_run"] is False


def test_performance_trends_endpoint(authenticated_client):
    """Test /admin/performance/trends."""
    response = authenticated_client.get(
        "/admin/performance/trends?pattern=code", headers=ADMIN_HEADERS
    )

    assert response.status_code == 200
    data = response.json()

    assert "pattern" in data
    assert "trends" in data
    assert isinstance(data["trends"], list)


def test_admin_endpoints_require_the_admin_key(auth_headers):
    """No key, a wrong key, or an ordinary user token never reaches the admin handlers."""
    client = TestClient(app)
    routes = [
        ("get", "/admin/feedback/summary"),
        ("get", "/admin/learning/status"),
        ("post", "/admin/learning/retrain"),
        ("get", "/admin/performance/trends?pattern=code"),
    ]
    for method, path in routes:
        assert getattr(client, method)(path).status_code == 401, path
        assert getattr(client, method)(path, headers=auth_headers).status_code == 401, path
        wrong = {"X-Admin-Key": "wrong"}
        assert getattr(client, method)(path, headers=wrong).status_code == 401, path
