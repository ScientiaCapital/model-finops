"""
Tests for Experiment Integration with Routing

This test suite validates A/B testing integration:
- Automatic user assignment during routing
- Strategy override based on experiment assignment
- Result recording after routing completion
- No interference when no experiments active
"""

import os
import sqlite3
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient

from app.main import app, routing_service

JWT_SECRET = "test-jwt-secret-for-testing-only"


class UserClient(TestClient):
    """Signs a token for the user_id in a /complete body. The service ignores the body field and
    uses the token subject, so these tests authenticate as the user they name."""

    def post(self, url, **kwargs):
        user = (kwargs.get("json") or {}).get("user_id")
        if url == "/complete" and user:
            token = jwt.encode(
                {
                    "sub": user,
                    "aud": "authenticated",
                    "exp": datetime.now(UTC) + timedelta(hours=1),
                },
                JWT_SECRET,
                algorithm="HS256",
            )
            kwargs["headers"] = {**kwargs.get("headers", {}), "Authorization": f"Bearer {token}"}
        return super().post(url, **kwargs)


client = UserClient(app)

# The no-user test posts anonymously, so anonymous /complete is on; the rest send tokens.
pytestmark = pytest.mark.usefixtures("allow_anonymous")


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", JWT_SECRET)


# Fixture to clean up experiments before each test
@pytest.fixture(autouse=True)
def clean_experiments_db():
    """Clean up experiment database before each test for isolation."""
    db_path = os.getenv("DATABASE_PATH", "optimizer.db")

    # Clean up before test
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM experiment_results")
        cursor.execute("DELETE FROM experiments")
        conn.commit()
        conn.close()
    except Exception:
        pass  # DB might not exist yet

    yield

    # Optionally clean up after test too
    # (keeping for now to see experiment state)


# Mock routing response fixture
@pytest.fixture
def mock_routing_response():
    """Mock successful routing response."""
    return {
        "request_id": "test_request_123",
        "response": "Test response from AI",
        "provider": "gemini",
        "model": "gemini-1.5-flash",
        "strategy_used": "complexity",
        "confidence": "medium",
        "complexity_metadata": {"score": 5, "reasons": ["simple"]},
        "routing_metadata": {"latency_ms": 150.5, "timestamp": time.time()},
        "tokens_in": 10,
        "tokens_out": 50,
        "cost": 0.001,
        "total_cost_today": 0.025,
        "cache_hit": False,
        "original_cost": None,
        "savings": 0.0,
        "cache_key": None,
    }


class TestExperimentIntegration:
    """Test experiment integration with routing flow."""

    @patch.object(routing_service, "route_and_complete", new_callable=AsyncMock)
    def test_routing_without_experiments(self, mock_route, mock_routing_response):
        """Normal routing works when no experiments active."""
        mock_route.return_value = mock_routing_response

        response = client.post(
            "/complete", json={"prompt": "What is 2+2?", "user_id": "test_user_123"}
        )

        assert response.status_code == 200
        # Should route normally without experiment interference
        assert mock_route.called

    @patch.object(routing_service, "route_and_complete", new_callable=AsyncMock)
    def test_routing_with_active_experiment(self, mock_route, mock_routing_response):
        """Routing uses experiment assignment when experiment active."""
        mock_route.return_value = mock_routing_response

        # Create experiment
        exp_response = client.post(
            "/experiments",
            json={
                "name": "Test Auto-Assignment",
                "control_strategy": "complexity",
                "test_strategy": "learning",
                "sample_size": 100,
            },
        )
        experiment_id = exp_response.json()["experiment_id"]

        # Make routing request with user_id
        response = client.post(
            "/complete", json={"prompt": "What is 2+2?", "user_id": "experiment_user_456"}
        )

        assert response.status_code == 200
        data = response.json()

        # Should have experiment metadata
        assert "experiment_id" in data
        assert data["experiment_id"] == experiment_id
        assert "assigned_strategy" in data
        assert data["assigned_strategy"] in ["complexity", "learning"]

    @patch.object(routing_service, "route_and_complete", new_callable=AsyncMock)
    def test_deterministic_strategy_assignment(self, mock_route, mock_routing_response):
        """Same user gets same strategy across multiple requests."""
        mock_route.return_value = mock_routing_response

        # Create experiment
        client.post(
            "/experiments",
            json={
                "name": "Deterministic Routing Test",
                "control_strategy": "complexity",
                "test_strategy": "learning",
                "sample_size": 100,
            },
        )

        # Make 3 requests with same user
        strategies = []
        for _ in range(3):
            response = client.post(
                "/complete", json={"prompt": "Test prompt", "user_id": "consistent_user_789"}
            )
            data = response.json()
            strategies.append(data.get("assigned_strategy"))

        # All should be the same
        assert len(set(strategies)) == 1  # All identical
        assert strategies[0] in ["complexity", "learning"]

    @patch.object(routing_service, "route_and_complete", new_callable=AsyncMock)
    def test_experiment_result_auto_recorded(self, mock_route, mock_routing_response):
        """Routing automatically records experiment result."""
        mock_route.return_value = mock_routing_response

        # Create experiment
        exp_response = client.post(
            "/experiments",
            json={
                "name": "Auto-Record Test",
                "control_strategy": "complexity",
                "test_strategy": "learning",
                "sample_size": 50,
            },
        )
        experiment_id = exp_response.json()["experiment_id"]

        # Get initial progress
        progress_before = client.get(f"/experiments/{experiment_id}/progress")
        initial_count = progress_before.json()["total_results"]

        # Make routing request
        client.post(
            "/complete", json={"prompt": "Test prompt for recording", "user_id": "record_test_user"}
        )

        # Check progress increased
        progress_after = client.get(f"/experiments/{experiment_id}/progress")
        final_count = progress_after.json()["total_results"]

        assert final_count == initial_count + 1

    @patch.object(routing_service, "route_and_complete", new_callable=AsyncMock)
    def test_experiment_result_includes_metrics(self, mock_route, mock_routing_response):
        """Recorded result includes latency, cost, quality."""
        mock_route.return_value = mock_routing_response

        # Create experiment
        exp_response = client.post(
            "/experiments",
            json={
                "name": "Metrics Test",
                "control_strategy": "complexity",
                "test_strategy": "learning",
                "sample_size": 50,
            },
        )
        experiment_id = exp_response.json()["experiment_id"]

        # Make routing request
        client.post("/complete", json={"prompt": "Metrics test prompt", "user_id": "metrics_user"})

        # Get summary
        summary = client.get(f"/experiments/{experiment_id}/summary")
        data = summary.json()

        # Should have recorded result with metrics
        total_count = data["control"]["count"] + data["test"]["count"]
        assert total_count == 1

        # Check that metrics are present
        if data["control"]["count"] > 0:
            assert data["control"]["avg_latency_ms"] > 0
            assert data["control"]["avg_cost_usd"] >= 0
        if data["test"]["count"] > 0:
            assert data["test"]["avg_latency_ms"] > 0
            assert data["test"]["avg_cost_usd"] >= 0

    @patch.object(routing_service, "route_and_complete", new_callable=AsyncMock)
    def test_multiple_active_experiments(self, mock_route, mock_routing_response):
        """Only first active experiment is used."""
        mock_route.return_value = mock_routing_response

        # Create two experiments
        exp1 = client.post(
            "/experiments",
            json={
                "name": "Experiment 1",
                "control_strategy": "complexity",
                "test_strategy": "learning",
                "sample_size": 50,
            },
        )
        exp1_id = exp1.json()["experiment_id"]

        exp2 = client.post(
            "/experiments",
            json={
                "name": "Experiment 2",
                "control_strategy": "learning",
                "test_strategy": "hybrid",
                "sample_size": 50,
            },
        )
        exp2.json()["experiment_id"]

        # Make routing request
        response = client.post(
            "/complete", json={"prompt": "Multi-experiment test", "user_id": "multi_exp_user"}
        )

        data = response.json()
        # Should use first experiment
        assert data["experiment_id"] == exp1_id

    @patch.object(routing_service, "route_and_complete", new_callable=AsyncMock)
    def test_routing_without_user_id(self, mock_route, mock_routing_response):
        """Routing without user_id skips experiments."""
        mock_route.return_value = mock_routing_response

        # Create experiment
        client.post(
            "/experiments",
            json={
                "name": "No User ID Test",
                "control_strategy": "complexity",
                "test_strategy": "learning",
                "sample_size": 50,
            },
        )

        # Make routing request WITHOUT user_id
        response = client.post("/complete", json={"prompt": "Test without user ID"})

        assert response.status_code == 200
        data = response.json()

        # Should not have experiment metadata
        assert data.get("experiment_id") is None
        assert data.get("assigned_strategy") is None


class TestExperimentCompletionFlow:
    """Test experiment lifecycle through completion."""

    @patch.object(routing_service, "route_and_complete", new_callable=AsyncMock)
    def test_experiment_reaches_sample_size(self, mock_route, mock_routing_response):
        """Experiment marked as complete when sample size reached."""
        mock_route.return_value = mock_routing_response

        # Create small experiment
        exp_response = client.post(
            "/experiments",
            json={
                "name": "Completion Test",
                "control_strategy": "complexity",
                "test_strategy": "learning",
                "sample_size": 5,
            },
        )
        experiment_id = exp_response.json()["experiment_id"]

        # Make 5 routing requests
        for i in range(5):
            client.post(
                "/complete", json={"prompt": f"Test prompt {i}", "user_id": f"completion_user_{i}"}
            )

        # Check progress
        progress = client.get(f"/experiments/{experiment_id}/progress")
        data = progress.json()

        assert data["total_results"] == 5
        assert data["is_complete"] is True

    @patch.object(routing_service, "route_and_complete", new_callable=AsyncMock)
    def test_completed_experiment_stops_recording(self, mock_route, mock_routing_response):
        """Completed experiments don't record new results."""
        mock_route.return_value = mock_routing_response

        # Create and complete experiment
        exp_response = client.post(
            "/experiments",
            json={
                "name": "Stop Recording Test",
                "control_strategy": "complexity",
                "test_strategy": "learning",
                "sample_size": 3,
            },
        )
        experiment_id = exp_response.json()["experiment_id"]

        # Fill to completion
        for i in range(3):
            client.post("/complete", json={"prompt": f"Fill {i}", "user_id": f"fill_user_{i}"})

        # Mark as completed
        client.post(f"/experiments/{experiment_id}/complete", json={"winner": "learning"})

        # Get count before
        progress_before = client.get(f"/experiments/{experiment_id}/progress")
        count_before = progress_before.json()["total_results"]

        # Try to record another result
        client.post(
            "/complete", json={"prompt": "Should not record", "user_id": "after_completion_user"}
        )

        # Count should not increase
        progress_after = client.get(f"/experiments/{experiment_id}/progress")
        count_after = progress_after.json()["total_results"]

        assert count_after == count_before  # No change
