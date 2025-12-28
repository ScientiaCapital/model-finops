"""
Tests for Forecasting API Endpoints.

Tests REST API functionality for cost forecasting and anomaly detection.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


class TestForecastEndpoint:
    """Tests for GET /forecasting/predict endpoint."""

    def test_forecast_requires_auth(self, client):
        """Forecast endpoint requires authentication."""
        response = client.get("/forecasting/predict")
        assert response.status_code == 401

    def test_forecast_with_auth(self, authenticated_client, auth_headers):
        """Forecast endpoint returns predictions with valid auth."""
        response = authenticated_client.get(
            "/forecasting/predict",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data
        assert "horizon_days" in data
        assert "daily_forecasts" in data
        assert "total_predicted_cost" in data

    def test_forecast_custom_horizon(self, authenticated_client, auth_headers):
        """Forecast respects horizon_days parameter."""
        response = authenticated_client.get(
            "/forecasting/predict?horizon_days=14",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["horizon_days"] == 14
        assert len(data["daily_forecasts"]) == 14

    def test_forecast_with_provider(self, authenticated_client, auth_headers):
        """Forecast accepts provider filter."""
        response = authenticated_client.get(
            "/forecasting/predict?provider=openai",
            headers=auth_headers,
        )
        assert response.status_code == 200

    def test_forecast_horizon_validation(self, authenticated_client, auth_headers):
        """Forecast validates horizon_days range."""
        # Too high
        response = authenticated_client.get(
            "/forecasting/predict?horizon_days=100",
            headers=auth_headers,
        )
        assert response.status_code == 422  # Validation error

        # Too low
        response = authenticated_client.get(
            "/forecasting/predict?horizon_days=0",
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestSummaryEndpoint:
    """Tests for GET /forecasting/summary endpoint."""

    def test_summary_requires_auth(self, client):
        """Summary endpoint requires authentication."""
        response = client.get("/forecasting/summary?monthly_budget=1000")
        assert response.status_code == 401

    def test_summary_with_auth(self, authenticated_client, auth_headers):
        """Summary endpoint returns complete data with valid auth."""
        response = authenticated_client.get(
            "/forecasting/summary?monthly_budget=1000",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "aggregate" in data
        assert "budget_projection" in data

    def test_summary_requires_budget(self, authenticated_client, auth_headers):
        """Summary requires monthly_budget parameter."""
        response = authenticated_client.get(
            "/forecasting/summary",
            headers=auth_headers,
        )
        assert response.status_code == 422  # Missing required param

    def test_summary_budget_validation(self, authenticated_client, auth_headers):
        """Summary validates budget is positive."""
        response = authenticated_client.get(
            "/forecasting/summary?monthly_budget=-100",
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestAnomaliesEndpoint:
    """Tests for GET /forecasting/anomalies endpoint."""

    def test_anomalies_requires_auth(self, client):
        """Anomalies endpoint requires authentication."""
        response = client.get("/forecasting/anomalies")
        assert response.status_code == 401

    def test_anomalies_with_auth(self, authenticated_client, auth_headers):
        """Anomalies endpoint returns list with valid auth."""
        response = authenticated_client.get(
            "/forecasting/anomalies",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "anomalies" in data
        assert "total_count" in data
        assert "unacknowledged_count" in data

    def test_anomalies_with_sensitivity(self, authenticated_client, auth_headers):
        """Anomalies respects sensitivity parameter."""
        response = authenticated_client.get(
            "/forecasting/anomalies?sensitivity=3.0",
            headers=auth_headers,
        )
        assert response.status_code == 200

    def test_anomalies_sensitivity_validation(self, authenticated_client, auth_headers):
        """Anomalies validates sensitivity range."""
        # Too high
        response = authenticated_client.get(
            "/forecasting/anomalies?sensitivity=5.0",
            headers=auth_headers,
        )
        assert response.status_code == 422

        # Too low
        response = authenticated_client.get(
            "/forecasting/anomalies?sensitivity=1.0",
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestAcknowledgeAnomalyEndpoint:
    """Tests for POST /forecasting/anomalies/{id}/acknowledge endpoint."""

    def test_acknowledge_requires_auth(self, client):
        """Acknowledge endpoint requires authentication."""
        response = client.post("/forecasting/anomalies/test-id/acknowledge")
        assert response.status_code == 401

    def test_acknowledge_not_found(self, authenticated_client, auth_headers):
        """Acknowledge returns 404 for non-existent anomaly."""
        response = authenticated_client.post(
            "/forecasting/anomalies/nonexistent-id/acknowledge",
            headers=auth_headers,
        )
        # Without Supabase, service returns False → 404
        assert response.status_code == 404


class TestBudgetExhaustionEndpoint:
    """Tests for GET /forecasting/budget-exhaustion endpoint."""

    def test_budget_exhaustion_requires_auth(self, client):
        """Budget exhaustion endpoint requires authentication."""
        response = client.get("/forecasting/budget-exhaustion?monthly_budget=1000")
        assert response.status_code == 401

    def test_budget_exhaustion_with_auth(self, authenticated_client, auth_headers):
        """Budget exhaustion returns projection with valid auth."""
        response = authenticated_client.get(
            "/forecasting/budget-exhaustion?monthly_budget=1000",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "monthly_budget" in data
        assert "current_spend" in data
        assert "percentage_used" in data
        assert "daily_burn_rate" in data
        assert "warning_level" in data
        assert "recommendation" in data
        assert data["monthly_budget"] == 1000.0

    def test_budget_exhaustion_requires_budget(self, authenticated_client, auth_headers):
        """Budget exhaustion requires monthly_budget parameter."""
        response = authenticated_client.get(
            "/forecasting/budget-exhaustion",
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestHealthEndpoint:
    """Tests for GET /forecasting/health endpoint."""

    def test_health_public(self, client):
        """Health check is public."""
        response = client.get("/forecasting/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "forecasting"
        assert "capabilities" in data

    def test_health_shows_capabilities(self, client):
        """Health check shows available capabilities."""
        response = client.get("/forecasting/health")
        data = response.json()
        caps = data["capabilities"]
        assert "forecast_methods" in caps
        assert "max_horizon_days" in caps
        assert caps["anomaly_detection"] is True
        assert caps["budget_projection"] is True
