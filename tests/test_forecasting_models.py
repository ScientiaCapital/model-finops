"""
Test suite for forecasting Pydantic models.
TDD: Tests written first, implementation follows.
"""
import pytest
from datetime import date, datetime
from pydantic import ValidationError


class TestForecastHorizon:
    """Test ForecastHorizon enum."""

    def test_horizon_values(self):
        """All expected horizons should be defined."""
        from app.models.forecasting import ForecastHorizon

        assert ForecastHorizon.WEEK.value == "7"
        assert ForecastHorizon.MONTH.value == "30"
        assert ForecastHorizon.QUARTER.value == "90"


class TestForecastMethod:
    """Test ForecastMethod enum."""

    def test_method_values(self):
        """All forecasting methods should be defined."""
        from app.models.forecasting import ForecastMethod

        expected = ["exp_smoothing", "moving_avg", "linear", "naive", "ensemble"]
        for method in expected:
            assert method in [m.value for m in ForecastMethod]


class TestAnomalySeverity:
    """Test AnomalySeverity enum."""

    def test_severity_levels(self):
        """All severity levels should be defined."""
        from app.models.forecasting import AnomalySeverity

        assert AnomalySeverity.LOW.value == "low"
        assert AnomalySeverity.MEDIUM.value == "medium"
        assert AnomalySeverity.HIGH.value == "high"
        assert AnomalySeverity.CRITICAL.value == "critical"


class TestForecastRequest:
    """Test ForecastRequest model."""

    def test_valid_request(self):
        """Should create valid forecast request."""
        from app.models.forecasting import ForecastRequest

        request = ForecastRequest(
            horizon_days=30,
            provider="gemini",
            include_confidence=True
        )

        assert request.horizon_days == 30
        assert request.provider == "gemini"

    def test_default_values(self):
        """Should have sensible defaults."""
        from app.models.forecasting import ForecastRequest

        request = ForecastRequest()

        assert request.horizon_days == 7  # Default 1 week
        assert request.provider is None  # Aggregate by default
        assert request.include_confidence is True

    def test_horizon_bounds(self):
        """Horizon must be between 1 and 90 days."""
        from app.models.forecasting import ForecastRequest

        # Valid bounds
        ForecastRequest(horizon_days=1)
        ForecastRequest(horizon_days=90)

        # Invalid
        with pytest.raises(ValidationError):
            ForecastRequest(horizon_days=0)

        with pytest.raises(ValidationError):
            ForecastRequest(horizon_days=91)


class TestDailyForecast:
    """Test DailyForecast model."""

    def test_valid_daily_forecast(self):
        """Should create valid daily forecast."""
        from app.models.forecasting import DailyForecast

        forecast = DailyForecast(
            date=date(2025, 1, 15),
            predicted_cost=25.50,
            lower_bound=20.00,
            upper_bound=31.00
        )

        assert forecast.predicted_cost == 25.50
        assert forecast.lower_bound < forecast.predicted_cost < forecast.upper_bound

    def test_bounds_validation(self):
        """Lower bound must be <= predicted <= upper bound."""
        from app.models.forecasting import DailyForecast

        # This should raise validation error - lower > predicted
        with pytest.raises(ValidationError):
            DailyForecast(
                date=date.today(),
                predicted_cost=10.0,
                lower_bound=15.0,  # Invalid - higher than predicted
                upper_bound=20.0
            )

    def test_non_negative_costs(self):
        """Costs cannot be negative."""
        from app.models.forecasting import DailyForecast

        with pytest.raises(ValidationError):
            DailyForecast(
                date=date.today(),
                predicted_cost=-5.0,  # Invalid
                lower_bound=-10.0,
                upper_bound=0.0
            )


class TestForecastResponse:
    """Test ForecastResponse model."""

    def test_valid_response(self):
        """Should create valid forecast response."""
        from app.models.forecasting import ForecastResponse, DailyForecast, ForecastMethod

        daily = [
            DailyForecast(
                date=date(2025, 1, i),
                predicted_cost=10.0 + i,
                lower_bound=8.0 + i,
                upper_bound=12.0 + i
            )
            for i in range(1, 8)
        ]

        response = ForecastResponse(
            user_id="user-123",
            generated_at=datetime.now(),
            horizon_days=7,
            method_used=ForecastMethod.EXP_SMOOTHING,
            data_points_used=30,
            total_predicted_cost=sum(d.predicted_cost for d in daily),
            daily_forecasts=daily,
            confidence_level=0.95,
            model_quality_score=0.15  # MAPE
        )

        assert len(response.daily_forecasts) == 7
        assert response.method_used == ForecastMethod.EXP_SMOOTHING

    def test_response_daily_count_matches_horizon(self):
        """Daily forecasts count should match horizon_days."""
        from app.models.forecasting import ForecastResponse, DailyForecast, ForecastMethod

        # 7-day horizon but only 3 daily forecasts - should validate
        daily = [
            DailyForecast(date=date(2025, 1, i), predicted_cost=10.0, lower_bound=8.0, upper_bound=12.0)
            for i in range(1, 4)
        ]

        with pytest.raises(ValidationError):
            ForecastResponse(
                user_id="user-123",
                generated_at=datetime.now(),
                horizon_days=7,  # Mismatch!
                method_used=ForecastMethod.MOVING_AVG,
                data_points_used=10,
                total_predicted_cost=30.0,
                daily_forecasts=daily,  # Only 3 days
                confidence_level=0.95
            )


class TestAnomalyDetectionRequest:
    """Test AnomalyDetectionRequest model."""

    def test_valid_request(self):
        """Should create valid anomaly detection request."""
        from app.models.forecasting import AnomalyDetectionRequest

        request = AnomalyDetectionRequest(
            lookback_days=30,
            sensitivity=2.5
        )

        assert request.lookback_days == 30
        assert request.sensitivity == 2.5

    def test_default_values(self):
        """Should have sensible defaults."""
        from app.models.forecasting import AnomalyDetectionRequest

        request = AnomalyDetectionRequest()

        assert request.lookback_days == 30
        assert request.sensitivity == 2.0  # Default z-score threshold

    def test_sensitivity_bounds(self):
        """Sensitivity must be between 1.5 and 4.0."""
        from app.models.forecasting import AnomalyDetectionRequest

        # Valid
        AnomalyDetectionRequest(sensitivity=1.5)
        AnomalyDetectionRequest(sensitivity=4.0)

        # Invalid
        with pytest.raises(ValidationError):
            AnomalyDetectionRequest(sensitivity=1.0)  # Too low

        with pytest.raises(ValidationError):
            AnomalyDetectionRequest(sensitivity=5.0)  # Too high


class TestAnomalyResponse:
    """Test AnomalyResponse model."""

    def test_valid_anomaly(self):
        """Should create valid anomaly response."""
        from app.models.forecasting import AnomalyResponse, AnomalySeverity

        anomaly = AnomalyResponse(
            id="anomaly-123",
            anomaly_date=date(2025, 1, 15),
            actual_cost=150.0,
            expected_cost=50.0,
            deviation_percent=200.0,
            z_score=3.5,
            severity=AnomalySeverity.HIGH,
            provider="anthropic",
            acknowledged=False
        )

        assert anomaly.severity == AnomalySeverity.HIGH
        assert anomaly.deviation_percent == 200.0

    def test_deviation_calculation(self):
        """Deviation percent should be correctly calculated."""
        from app.models.forecasting import AnomalyResponse, AnomalySeverity

        anomaly = AnomalyResponse(
            id="test",
            anomaly_date=date.today(),
            actual_cost=100.0,
            expected_cost=50.0,
            deviation_percent=100.0,  # (100-50)/50 * 100
            z_score=2.5,
            severity=AnomalySeverity.MEDIUM,
            acknowledged=False
        )

        # Verify calculation
        calculated = (anomaly.actual_cost - anomaly.expected_cost) / anomaly.expected_cost * 100
        assert abs(anomaly.deviation_percent - calculated) < 0.1


class TestAnomalyListResponse:
    """Test AnomalyListResponse model."""

    def test_valid_list_response(self):
        """Should create valid anomaly list response."""
        from app.models.forecasting import AnomalyListResponse, AnomalyResponse, AnomalySeverity

        anomalies = [
            AnomalyResponse(
                id=f"a-{i}",
                anomaly_date=date(2025, 1, i),
                actual_cost=100.0,
                expected_cost=50.0,
                deviation_percent=100.0,
                z_score=2.5,
                severity=AnomalySeverity.MEDIUM,
                acknowledged=(i % 2 == 0)
            )
            for i in range(1, 6)
        ]

        response = AnomalyListResponse(
            anomalies=anomalies,
            total_count=5,
            unacknowledged_count=3  # 1, 3, 5 are unacknowledged
        )

        assert response.total_count == 5
        assert response.unacknowledged_count == 3


class TestBudgetExhaustionResponse:
    """Test BudgetExhaustionResponse model."""

    def test_valid_response(self):
        """Should create valid budget exhaustion response."""
        from app.models.forecasting import BudgetExhaustionResponse

        response = BudgetExhaustionResponse(
            user_id="user-123",
            monthly_budget=1000.0,
            current_spend=750.0,
            percentage_used=75.0,
            daily_burn_rate=25.0,
            projected_exhaustion_date=date(2025, 1, 20),
            days_until_exhaustion=10,
            confidence_percentage=85.0,
            warning_level="warning",
            recommendation="Consider reducing usage or increasing budget."
        )

        assert response.percentage_used == 75.0
        assert response.warning_level == "warning"

    def test_warning_levels(self):
        """Warning level must be valid."""
        from app.models.forecasting import BudgetExhaustionResponse

        valid_levels = ["safe", "caution", "warning", "critical"]

        for level in valid_levels:
            response = BudgetExhaustionResponse(
                user_id="test",
                monthly_budget=100.0,
                current_spend=50.0,
                percentage_used=50.0,
                daily_burn_rate=5.0,
                confidence_percentage=90.0,
                warning_level=level,
                recommendation="Test"
            )
            assert response.warning_level == level

    def test_no_exhaustion_date(self):
        """Exhaustion date can be None if budget won't be exhausted."""
        from app.models.forecasting import BudgetExhaustionResponse

        response = BudgetExhaustionResponse(
            user_id="user-123",
            monthly_budget=1000.0,
            current_spend=100.0,
            percentage_used=10.0,
            daily_burn_rate=2.0,
            projected_exhaustion_date=None,  # Won't exhaust
            days_until_exhaustion=None,
            confidence_percentage=95.0,
            warning_level="safe",
            recommendation="Budget is healthy."
        )

        assert response.projected_exhaustion_date is None
        assert response.days_until_exhaustion is None


class TestForecastSummaryResponse:
    """Test ForecastSummaryResponse model."""

    def test_valid_summary(self):
        """Should create valid forecast summary."""
        from app.models.forecasting import (
            ForecastSummaryResponse, ForecastResponse,
            BudgetExhaustionResponse, AnomalyResponse,
            DailyForecast, ForecastMethod, AnomalySeverity
        )

        daily = [
            DailyForecast(date=date(2025, 1, i), predicted_cost=10.0, lower_bound=8.0, upper_bound=12.0)
            for i in range(1, 8)
        ]

        aggregate = ForecastResponse(
            user_id="user-123",
            generated_at=datetime.now(),
            horizon_days=7,
            method_used=ForecastMethod.EXP_SMOOTHING,
            data_points_used=30,
            total_predicted_cost=70.0,
            daily_forecasts=daily,
            confidence_level=0.95
        )

        budget = BudgetExhaustionResponse(
            user_id="user-123",
            monthly_budget=500.0,
            current_spend=200.0,
            percentage_used=40.0,
            daily_burn_rate=10.0,
            confidence_percentage=90.0,
            warning_level="safe",
            recommendation="On track."
        )

        summary = ForecastSummaryResponse(
            aggregate=aggregate,
            by_provider=[],  # No per-provider breakdowns
            budget_projection=budget,
            recent_anomalies=[]
        )

        assert summary.aggregate.total_predicted_cost == 70.0
        assert summary.budget_projection.warning_level == "safe"


class TestWarningLevel:
    """Test warning level determination logic."""

    def test_safe_level(self):
        """Under 50% should be safe."""
        from app.models.forecasting import BudgetExhaustionResponse

        response = BudgetExhaustionResponse(
            user_id="test",
            monthly_budget=100.0,
            current_spend=40.0,
            percentage_used=40.0,
            daily_burn_rate=2.0,
            confidence_percentage=90.0,
            warning_level="safe",
            recommendation="OK"
        )
        assert response.warning_level == "safe"

    def test_caution_level(self):
        """50-75% should be caution."""
        from app.models.forecasting import BudgetExhaustionResponse

        response = BudgetExhaustionResponse(
            user_id="test",
            monthly_budget=100.0,
            current_spend=60.0,
            percentage_used=60.0,
            daily_burn_rate=3.0,
            confidence_percentage=90.0,
            warning_level="caution",
            recommendation="Monitor usage"
        )
        assert response.warning_level == "caution"

    def test_warning_level_value(self):
        """75-90% should be warning."""
        from app.models.forecasting import BudgetExhaustionResponse

        response = BudgetExhaustionResponse(
            user_id="test",
            monthly_budget=100.0,
            current_spend=85.0,
            percentage_used=85.0,
            daily_burn_rate=5.0,
            confidence_percentage=90.0,
            warning_level="warning",
            recommendation="Reduce usage"
        )
        assert response.warning_level == "warning"

    def test_critical_level(self):
        """Over 90% should be critical."""
        from app.models.forecasting import BudgetExhaustionResponse

        response = BudgetExhaustionResponse(
            user_id="test",
            monthly_budget=100.0,
            current_spend=95.0,
            percentage_used=95.0,
            daily_burn_rate=5.0,
            confidence_percentage=90.0,
            warning_level="critical",
            recommendation="Budget almost exhausted!"
        )
        assert response.warning_level == "critical"
