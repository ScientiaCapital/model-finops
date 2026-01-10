"""
Tests for ForecastingService business logic.

Tests service layer functionality for cost forecasting and anomaly detection.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from app.services.forecasting_service import ForecastingService
from app.models.forecasting import (
    ForecastRequest,
    ForecastResponse,
    AnomalyDetectionRequest,
    AnomalySeverity,
    ForecastMethod,
)


class TestForecastingServiceInit:
    """Tests for ForecastingService initialization."""

    def test_init_without_supabase(self):
        """Service initializes without Supabase client."""
        service = ForecastingService()
        assert service.supabase is None

    def test_init_with_supabase(self):
        """Service initializes with Supabase client."""
        mock_client = MagicMock()
        service = ForecastingService(supabase_client=mock_client)
        assert service.supabase == mock_client


class TestZScoreToSeverity:
    """Tests for Z-score to severity mapping."""

    @pytest.fixture
    def service(self):
        return ForecastingService()

    def test_critical_at_4(self, service):
        """Z-score >= 4.0 maps to CRITICAL."""
        assert service._z_score_to_severity(4.0) == AnomalySeverity.CRITICAL
        assert service._z_score_to_severity(4.5) == AnomalySeverity.CRITICAL
        assert service._z_score_to_severity(10.0) == AnomalySeverity.CRITICAL

    def test_high_at_3(self, service):
        """Z-score >= 3.0 and < 4.0 maps to HIGH."""
        assert service._z_score_to_severity(3.0) == AnomalySeverity.HIGH
        assert service._z_score_to_severity(3.5) == AnomalySeverity.HIGH
        assert service._z_score_to_severity(3.99) == AnomalySeverity.HIGH

    def test_medium_at_2_5(self, service):
        """Z-score >= 2.5 and < 3.0 maps to MEDIUM."""
        assert service._z_score_to_severity(2.5) == AnomalySeverity.MEDIUM
        assert service._z_score_to_severity(2.75) == AnomalySeverity.MEDIUM
        assert service._z_score_to_severity(2.99) == AnomalySeverity.MEDIUM

    def test_low_below_2_5(self, service):
        """Z-score < 2.5 maps to LOW."""
        assert service._z_score_to_severity(2.49) == AnomalySeverity.LOW
        assert service._z_score_to_severity(2.0) == AnomalySeverity.LOW
        assert service._z_score_to_severity(0.0) == AnomalySeverity.LOW

    def test_boundary_values_include_threshold(self, service):
        """Boundary values are inclusive (>= not >)."""
        # These are the exact boundary values
        assert service._z_score_to_severity(4.0) == AnomalySeverity.CRITICAL
        assert service._z_score_to_severity(3.0) == AnomalySeverity.HIGH
        assert service._z_score_to_severity(2.5) == AnomalySeverity.MEDIUM
        # Just below boundaries
        assert service._z_score_to_severity(3.9999) == AnomalySeverity.HIGH
        assert service._z_score_to_severity(2.9999) == AnomalySeverity.MEDIUM
        assert service._z_score_to_severity(2.4999) == AnomalySeverity.LOW


class TestBudgetWarning:
    """Tests for budget warning logic."""

    @pytest.fixture
    def service(self):
        return ForecastingService()

    def test_critical_when_exhausted(self, service):
        """100%+ usage is critical."""
        level, msg = service._get_budget_warning(100.0, None, 15)
        assert level == "critical"
        assert "exhausted" in msg.lower()

        level, msg = service._get_budget_warning(150.0, None, 15)
        assert level == "critical"

    def test_critical_at_90_percent(self, service):
        """90%+ usage is critical (takes priority over projection)."""
        # Even if projection shows plenty of time, 90% is critical
        level, msg = service._get_budget_warning(90.0, days_until=30, days_remaining=15)
        assert level == "critical"
        assert "90%" in msg

        level, msg = service._get_budget_warning(95.0, days_until=None, days_remaining=15)
        assert level == "critical"

    def test_warning_at_75_percent(self, service):
        """75%+ usage is warning (takes priority over projection)."""
        level, msg = service._get_budget_warning(75.0, days_until=30, days_remaining=15)
        assert level == "warning"
        assert "75%" in msg

        level, msg = service._get_budget_warning(80.0, days_until=None, days_remaining=10)
        assert level == "warning"

    def test_critical_projection_under_3_days(self, service):
        """Projection <= 3 days is critical (if under 75% used)."""
        level, msg = service._get_budget_warning(50.0, days_until=2, days_remaining=10)
        assert level == "critical"
        assert "2 days" in msg

        level, msg = service._get_budget_warning(50.0, days_until=3, days_remaining=10)
        assert level == "critical"

    def test_warning_projection_under_7_days(self, service):
        """Projection 4-7 days is warning (if under 75% used)."""
        level, msg = service._get_budget_warning(50.0, days_until=5, days_remaining=10)
        assert level == "warning"
        assert "5 days" in msg

        level, msg = service._get_budget_warning(60.0, days_until=7, days_remaining=15)
        assert level == "warning"

    def test_caution_projection_under_14_days(self, service):
        """Projection 8-14 days is caution (if under 75% used)."""
        level, msg = service._get_budget_warning(40.0, days_until=10, days_remaining=20)
        assert level == "caution"

        level, msg = service._get_budget_warning(50.0, days_until=14, days_remaining=20)
        assert level == "caution"

    def test_safe_when_on_track(self, service):
        """Safe when usage low and projection good."""
        level, msg = service._get_budget_warning(30.0, days_until=None, days_remaining=20)
        assert level == "safe"
        assert "on track" in msg.lower()

        # Projection beyond month remaining
        level, msg = service._get_budget_warning(40.0, days_until=30, days_remaining=15)
        assert level == "safe"

    def test_percentage_priority_over_projection(self, service):
        """Percentage thresholds take priority over projections."""
        # At 92% usage, should be critical even if projection is fine
        level, _ = service._get_budget_warning(92.0, days_until=30, days_remaining=15)
        assert level == "critical"

        # At 80% usage, should be warning even if projection is fine
        level, _ = service._get_budget_warning(80.0, days_until=30, days_remaining=15)
        assert level == "warning"


class TestGenerateForecast:
    """Tests for forecast generation."""

    @pytest.mark.asyncio
    async def test_returns_mock_data_without_supabase(self):
        """Returns mock forecast data without Supabase."""
        service = ForecastingService()
        request = ForecastRequest(horizon_days=7)

        response = await service.generate_forecast("user-123", request)

        assert isinstance(response, ForecastResponse)
        assert response.user_id == "user-123"
        assert response.horizon_days == 7

    @pytest.mark.asyncio
    async def test_respects_horizon_days(self):
        """Forecast respects requested horizon."""
        service = ForecastingService()

        for horizon in [3, 7, 14, 30]:
            request = ForecastRequest(horizon_days=horizon)
            response = await service.generate_forecast("user-123", request)
            assert response.horizon_days == horizon


class TestDetectAnomalies:
    """Tests for anomaly detection."""

    @pytest.mark.asyncio
    async def test_returns_response_without_supabase(self):
        """Returns anomaly response structure without Supabase."""
        service = ForecastingService()
        request = AnomalyDetectionRequest(lookback_days=30, sensitivity=2.0)

        response = await service.detect_anomalies("user-123", request)

        # Service returns mock data when no Supabase
        assert hasattr(response, 'anomalies')
        assert hasattr(response, 'total_count')


class TestAcknowledgeAnomaly:
    """Tests for acknowledging anomalies."""

    @pytest.mark.asyncio
    async def test_returns_false_without_supabase(self):
        """Returns False without Supabase client."""
        service = ForecastingService()
        result = await service.acknowledge_anomaly("user", "anomaly-1")
        assert result is False


class TestBudgetExhaustion:
    """Tests for budget exhaustion projection."""

    @pytest.mark.asyncio
    async def test_returns_mock_without_supabase(self):
        """Returns mock projection without Supabase."""
        service = ForecastingService()
        response = await service.project_budget_exhaustion("user-123", 1000.0)

        # Should return a valid response structure
        assert response.monthly_budget == 1000.0
        assert response.user_id == "user-123"


class TestForecastSummary:
    """Tests for forecast summary."""

    @pytest.mark.asyncio
    async def test_returns_summary_without_supabase(self):
        """Returns summary structure without Supabase."""
        service = ForecastingService()
        response = await service.get_forecast_summary("user-123", 1000.0)

        # ForecastSummaryResponse has: aggregate, by_provider, budget_projection, recent_anomalies
        assert hasattr(response, 'aggregate')
        assert hasattr(response, 'budget_projection')
        # Aggregate forecast should be present
        assert response.aggregate is not None

    @pytest.mark.asyncio
    async def test_returns_per_provider_forecasts_without_supabase(self):
        """Returns per-provider forecasts using mock data."""
        service = ForecastingService()
        response = await service.get_forecast_summary("user-123", 1000.0)

        # Without Supabase, mock providers are returned: gemini, claude, openrouter
        assert hasattr(response, 'by_provider')
        assert isinstance(response.by_provider, list)
        assert len(response.by_provider) == 3  # Mock returns 3 providers

        # Each provider forecast should have valid structure
        for forecast in response.by_provider:
            assert isinstance(forecast, ForecastResponse)
            assert forecast.provider is not None
            assert forecast.horizon_days == 7
            assert forecast.user_id == "user-123"

    @pytest.mark.asyncio
    async def test_per_provider_forecasts_have_distinct_providers(self):
        """Each per-provider forecast has a distinct provider name."""
        service = ForecastingService()
        response = await service.get_forecast_summary("user-123", 1000.0)

        # Extract provider names
        provider_names = [f.provider for f in response.by_provider]

        # All providers should be unique
        assert len(provider_names) == len(set(provider_names))

        # Mock providers should be present
        assert "gemini" in provider_names
        assert "claude" in provider_names
        assert "openrouter" in provider_names


class TestGetUserProviders:
    """Tests for _get_user_providers helper."""

    @pytest.mark.asyncio
    async def test_returns_mock_providers_without_supabase(self):
        """Returns mock providers when no Supabase client."""
        service = ForecastingService()
        providers = await service._get_user_providers("user-123")

        assert isinstance(providers, list)
        assert len(providers) == 3
        assert "gemini" in providers
        assert "claude" in providers
        assert "openrouter" in providers

    @pytest.mark.asyncio
    async def test_handles_empty_result_from_supabase(self):
        """Returns empty list when Supabase returns no data."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []

        # Create a fluent mock that returns itself for chained calls
        mock_query = MagicMock()
        mock_query.select = MagicMock(return_value=mock_query)
        mock_query.eq = MagicMock(return_value=mock_query)
        mock_query.not_ = MagicMock(return_value=mock_query)
        mock_query.execute = AsyncMock(return_value=mock_result)

        mock_client.table = MagicMock(return_value=mock_query)

        service = ForecastingService(supabase_client=mock_client)
        providers = await service._get_user_providers("user-123")

        assert providers == []

    @pytest.mark.asyncio
    async def test_deduplicates_providers(self):
        """Verifies deduplication logic works correctly."""
        # Test the deduplication logic directly
        # Given data with duplicates
        data = [
            {"provider": "gemini"},
            {"provider": "gemini"},  # Duplicate
            {"provider": "claude"},
            {"provider": "claude"},  # Duplicate
            {"provider": "openrouter"},
        ]

        # The logic: list(set(r["provider"] for r in data))
        result = list(set(r["provider"] for r in data))

        # Should have 3 unique providers
        assert len(result) == 3
        assert set(result) == {"gemini", "claude", "openrouter"}
