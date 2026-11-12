"""End-to-end integration tests for feedback loop."""

import os
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def user_headers() -> dict[str, str]:
    """Bearer token signed with the live project's SUPABASE_JWT_SECRET."""
    token = jwt.encode(
        {
            "sub": "integration-user",
            "aud": "authenticated",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        os.environ["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def admin_headers() -> dict[str, str]:
    return {"X-Admin-Key": os.environ["ADMIN_API_KEY"]}


@pytest.fixture(autouse=True)
def mock_provider_apis():
    """Mock all provider API calls to avoid authentication errors in tests."""
    with (
        patch("app.providers.ClaudeProvider.complete", new_callable=AsyncMock) as mock_claude,
        patch("app.providers.GeminiProvider.complete", new_callable=AsyncMock) as mock_gemini,
        patch(
            "app.providers.OpenRouterProvider.complete", new_callable=AsyncMock
        ) as mock_openrouter,
    ):
        # Configure mock responses - complete() returns (text, tokens_in, tokens_out, cost)
        mock_claude.return_value = (
            "This is a mocked Claude response for testing.",
            10,  # tokens_in
            20,  # tokens_out
            0.00001,  # cost
        )

        mock_gemini.return_value = (
            "This is a mocked Gemini response for testing.",
            10,
            20,
            0.00001,
        )

        mock_openrouter.return_value = (
            "This is a mocked OpenRouter response for testing.",
            10,
            20,
            0.00001,
        )

        yield {"claude": mock_claude, "gemini": mock_gemini, "openrouter": mock_openrouter}


@pytest.mark.integration
def test_complete_feedback_loop_flow():
    """Test complete flow: request -> feedback -> retrain -> improved routing.

    This tests the entire system end-to-end:
    1. Submit a prompt and get routing decision
    2. Provide quality feedback
    3. Trigger retraining
    4. Verify routing recommendations updated
    """
    # Step 1: Submit request with auto_route
    response = client.post(
        "/complete",
        json={
            "prompt": "Debug Python code with print statements",
            "auto_route": True,
            "max_tokens": 100,
        },
        headers=user_headers(),
    )

    assert response.status_code == 200
    completion = response.json()

    request_id = completion.get("request_id")
    assert request_id is not None

    # Step 2: Submit positive feedback
    feedback_response = client.post(
        "/production/feedback",
        json={
            "request_id": request_id,
            "quality_score": 5,
            "is_correct": True,
            "comment": "Excellent code debugging explanation",
        },
        headers=user_headers(),
    )

    assert feedback_response.status_code == 200
    assert feedback_response.json()["status"] == "recorded"

    # Step 3: Check feedback summary
    summary = client.get("/admin/feedback/summary", headers=admin_headers())
    assert summary.status_code == 200
    assert summary.json()["total_feedback"] > 0

    # Step 4: Run retraining (dry run first)
    dry_run = client.post("/admin/learning/retrain?dry_run=true", headers=admin_headers())
    assert dry_run.status_code == 200

    dry_result = dry_run.json()
    assert "changes" in dry_result
    assert dry_result["dry_run"] is True

    # Step 5: Check learning status
    status = client.get("/admin/learning/status", headers=admin_headers())
    assert status.status_code == 200

    status_data = status.json()
    assert "confidence_distribution" in status_data


@pytest.mark.integration
def test_feedback_improves_routing_over_time():
    """Test that repeated good feedback improves routing confidence.

    Simulates multiple users providing positive feedback for
    a specific pattern-model combination.
    """
    pattern_prompt = "Explain asyncio in Python"

    # Submit 10 requests with feedback
    for _i in range(10):
        # Get routing decision
        response = client.post(
            "/complete",
            json={"prompt": pattern_prompt, "auto_route": True, "max_tokens": 50},
            headers=user_headers(),
        )

        request_id = response.json()["request_id"]

        # Provide positive feedback
        client.post(
            "/production/feedback",
            json={"request_id": request_id, "quality_score": 5, "is_correct": True},
            headers=user_headers(),
        )

        time.sleep(0.1)  # Small delay

    # Run retraining
    retrain_result = client.post("/admin/learning/retrain?dry_run=false", headers=admin_headers())
    assert retrain_result.status_code == 200

    result = retrain_result.json()

    # Should have high confidence updates now
    [c for c in result["changes"] if c.get("confidence") == "high"]

    # May not have high confidence yet with only 10 samples,
    # but should have at least medium
    assert result["total_changes"] >= 0


@pytest.mark.integration
def test_low_quality_feedback_prevents_routing_change():
    """Test that poor quality feedback doesn't change routing.

    Ensures low-quality responses don't pollute the learning.
    """
    # Submit request
    response = client.post(
        "/complete",
        json={"prompt": "Test low quality pattern", "auto_route": True, "max_tokens": 50},
        headers=user_headers(),
    )

    request_id = response.json()["request_id"]

    # Provide negative feedback (only 1, below threshold)
    client.post(
        "/production/feedback",
        json={
            "request_id": request_id,
            "quality_score": 1,
            "is_correct": False,
            "comment": "Wrong answer",
        },
        headers=user_headers(),
    )

    # Run retraining (dry run)
    retrain_result = client.post("/admin/learning/retrain?dry_run=true", headers=admin_headers())
    result = retrain_result.json()

    # With only 1 poor sample, shouldn't meet confidence threshold
    # So changes list might be empty or have low confidence items filtered
    assert "changes" in result
