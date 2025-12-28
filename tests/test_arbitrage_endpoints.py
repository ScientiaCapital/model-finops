"""
Tests for Arbitrage API Endpoints.

Tests REST API functionality for cost arbitrage and model switching.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


class TestAnalyzeEndpoint:
    """Tests for POST /arbitrage/analyze endpoint."""

    def test_analyze_requires_auth(self, client):
        """Analyze endpoint requires authentication."""
        response = client.post("/arbitrage/analyze", json={
            "prompt": "Test prompt",
            "current_model": "claude-3-opus",
        })
        assert response.status_code == 401

    def test_analyze_with_auth(self, authenticated_client, auth_headers):
        """Analyze endpoint returns opportunities with valid auth."""
        response = authenticated_client.post(
            "/arbitrage/analyze",
            json={
                "prompt": "Write a Python function",
                "current_model": "claude-3-opus",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "current_model" in data
        assert "opportunities" in data
        assert "current_cost" in data
        assert data["current_model"] == "claude-3-opus"

    def test_analyze_with_token_counts(self, authenticated_client, auth_headers):
        """Analyze endpoint accepts token counts."""
        response = authenticated_client.post(
            "/arbitrage/analyze",
            json={
                "prompt": "Test prompt",
                "current_model": "gpt-4",
                "input_tokens": 100,
                "output_tokens": 200,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "current_cost" in data

    def test_analyze_unknown_model(self, authenticated_client, auth_headers):
        """Analyze returns empty opportunities for unknown models."""
        response = authenticated_client.post(
            "/arbitrage/analyze",
            json={
                "prompt": "Test",
                "current_model": "unknown-model-xyz",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["opportunities"] == []
        assert data["current_cost"] == 0.0


class TestModelsEndpoint:
    """Tests for GET /arbitrage/models endpoint."""

    def test_list_models_public(self, client):
        """Models list is public (no auth required)."""
        response = client.get("/arbitrage/models")
        assert response.status_code == 200
        data = response.json()
        # Endpoint returns list directly
        assert isinstance(data, list)
        assert len(data) > 0

    def test_list_models_structure(self, client):
        """Models have expected structure."""
        response = client.get("/arbitrage/models")
        data = response.json()
        assert isinstance(data, list)
        if data:
            model = data[0]
            assert "model_id" in model
            assert "provider" in model
            assert "input_price_per_million" in model
            assert "output_price_per_million" in model


class TestModelAlternativesEndpoint:
    """Tests for GET /arbitrage/models/{model_id}/alternatives endpoint."""

    def test_alternatives_public(self, client):
        """Alternatives endpoint is public (no auth required)."""
        response = client.get("/arbitrage/models/claude-3-5-sonnet-20241022/alternatives")
        assert response.status_code == 200

    def test_alternatives_returns_list(self, client):
        """Alternatives endpoint returns list of models."""
        response = client.get("/arbitrage/models/claude-3-5-sonnet-20241022/alternatives")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_alternatives_unknown_model(self, client):
        """Alternatives returns empty list for unknown model."""
        response = client.get("/arbitrage/models/unknown-model/alternatives")
        assert response.status_code == 200
        data = response.json()
        assert data == []


class TestSavingsReportEndpoint:
    """Tests for GET /arbitrage/savings-report endpoint."""

    def test_savings_requires_auth(self, client):
        """Savings report endpoint requires authentication."""
        response = client.get("/arbitrage/savings-report")
        assert response.status_code == 401

    def test_savings_with_auth(self, authenticated_client, auth_headers):
        """Savings report returns data with valid auth."""
        response = authenticated_client.get(
            "/arbitrage/savings-report",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_potential_savings" in data
        assert "actual_savings" in data
        assert "opportunities_found" in data
        assert "opportunities_applied" in data

    def test_savings_with_days_param(self, authenticated_client, auth_headers):
        """Savings report respects days parameter."""
        response = authenticated_client.get(
            "/arbitrage/savings-report?days=7",
            headers=auth_headers,
        )
        assert response.status_code == 200


class TestOpportunitiesEndpoint:
    """Tests for GET /arbitrage/opportunities endpoint."""

    def test_opportunities_requires_auth(self, client):
        """Opportunities endpoint requires authentication."""
        response = client.get("/arbitrage/opportunities")
        assert response.status_code == 401

    def test_opportunities_with_auth(self, authenticated_client, auth_headers):
        """Opportunities endpoint returns list with valid auth."""
        response = authenticated_client.get(
            "/arbitrage/opportunities",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        # Endpoint returns list directly
        assert isinstance(data, list)

    def test_opportunities_with_limit(self, authenticated_client, auth_headers):
        """Opportunities respects limit parameter."""
        response = authenticated_client.get(
            "/arbitrage/opportunities?limit=5",
            headers=auth_headers,
        )
        assert response.status_code == 200


class TestModelsByProviderEndpoint:
    """Tests for GET /arbitrage/models/by-provider/{provider} endpoint."""

    def test_models_by_provider_public(self, client):
        """Models by provider is public."""
        response = client.get("/arbitrage/models/by-provider/gemini")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        for model in data:
            assert model["provider"] == "gemini"

    def test_models_by_unknown_provider(self, client):
        """Returns 404 for unknown provider."""
        response = client.get("/arbitrage/models/by-provider/unknown-provider")
        assert response.status_code == 404


class TestModelsByCapabilityEndpoint:
    """Tests for GET /arbitrage/models/by-capability/{capability} endpoint."""

    def test_models_by_capability_public(self, client):
        """Models by capability is public."""
        response = client.get("/arbitrage/models/by-capability/code_gen")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_models_by_invalid_capability(self, client):
        """Returns 400 for invalid capability."""
        response = client.get("/arbitrage/models/by-capability/invalid_cap")
        assert response.status_code == 400


class TestCheapestModelEndpoint:
    """Tests for GET /arbitrage/cheapest/{capability} endpoint."""

    def test_cheapest_public(self, client):
        """Cheapest model is public."""
        response = client.get("/arbitrage/cheapest/code_gen")
        assert response.status_code == 200
        data = response.json()
        assert "model_id" in data
        assert "provider" in data

    def test_cheapest_invalid_capability(self, client):
        """Returns 400 for invalid capability."""
        response = client.get("/arbitrage/cheapest/invalid_cap")
        assert response.status_code == 400
