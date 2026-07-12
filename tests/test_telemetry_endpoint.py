"""
Tests for POST /api/telemetry/ingest.

Mocks AsyncCostTracker.log_request entirely — this endpoint's job is just to
validate the token and payload shape and forward to log_request(), so these
tests don't need a live Supabase connection (matters since Supabase access
here can be toggled on/off independent of running tests).

Uses a minimal FastAPI app with only the telemetry router mounted, rather than
importing the full app.main — main.py pulls in the entire dependency tree
(Stripe, scipy, sentence-transformers, ...) which is unrelated to what this
router actually does.
"""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import telemetry

app = FastAPI()
app.include_router(telemetry.router)

VALID_PAYLOAD = {
    "provider": "ollama",
    "model": "ollama/qwen2.5:14b",
    "input_tokens": 120,
    "output_tokens": 45,
    "cost_usd": 0.0,
    "task_type": "did recording start in room 320-B",
    "session_id": "sess-123",
    "project_id": "av-demo",
    "latency_ms": 850,
    "source": "silkroute",
}


@pytest.fixture
def telemetry_client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _set_ingest_token(monkeypatch):
    monkeypatch.setenv("FINOPS_INGEST_TOKEN", "test-secret-token")


class TestIngestAuth:
    def test_missing_token_returns_401(self, telemetry_client):
        response = telemetry_client.post("/api/telemetry/ingest", json=VALID_PAYLOAD)
        assert response.status_code == 401

    def test_wrong_token_returns_401(self, telemetry_client):
        response = telemetry_client.post(
            "/api/telemetry/ingest",
            json=VALID_PAYLOAD,
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert response.status_code == 401

    def test_no_configured_token_returns_401(self, telemetry_client, monkeypatch):
        monkeypatch.delenv("FINOPS_INGEST_TOKEN", raising=False)
        response = telemetry_client.post(
            "/api/telemetry/ingest",
            json=VALID_PAYLOAD,
            headers={"Authorization": "Bearer anything"},
        )
        assert response.status_code == 401


class TestIngestSuccess:
    def test_valid_payload_returns_200_and_calls_log_request(self, telemetry_client):
        with patch(
            "app.routers.telemetry._cost_tracker.log_request",
            new=AsyncMock(return_value={"id": 1}),
        ) as mock_log:
            response = telemetry_client.post(
                "/api/telemetry/ingest",
                json=VALID_PAYLOAD,
                headers={"Authorization": "Bearer test-secret-token"},
            )
        assert response.status_code == 200
        assert response.json()["status"] == "logged"
        mock_log.assert_awaited_once()
        _, kwargs = mock_log.call_args
        assert kwargs["provider"] == "ollama"
        assert kwargs["model"] == "ollama/qwen2.5:14b"
        assert kwargs["tokens_in"] == 120
        assert kwargs["tokens_out"] == 45
        assert kwargs["cost"] == 0.0
        assert kwargs["project_id"] == "av-demo"
        assert kwargs["session_id"] == "sess-123"
        assert kwargs["latency_ms"] == 850

    def test_minimal_payload_optional_fields_omitted(self, telemetry_client):
        minimal = {
            "provider": "ollama",
            "model": "ollama/qwen3:30b-a3b",
            "input_tokens": 10,
            "output_tokens": 5,
            "cost_usd": 0.0,
        }
        with patch(
            "app.routers.telemetry._cost_tracker.log_request",
            new=AsyncMock(return_value={"id": 2}),
        ) as mock_log:
            response = telemetry_client.post(
                "/api/telemetry/ingest",
                json=minimal,
                headers={"Authorization": "Bearer test-secret-token"},
            )
        assert response.status_code == 200
        mock_log.assert_awaited_once()
