"""
Test suite for forecasting algorithms.
TDD: Tests written first, implementation follows.
"""
import pytest
import numpy as np
from datetime import date, timedelta


class TestForecastResult:
    """Test ForecastResult dataclass."""

    def test_forecast_result_creation(self):
        """Should create valid forecast result."""
        from app.forecasting.algorithms import ForecastResult

        result = ForecastResult(
            predictions=np.array([10.0, 11.0, 12.0]),
            lower_bounds=np.array([8.0, 9.0, 10.0]),
            upper_bounds=np.array([12.0, 13.0, 14.0]),
            method="exp_smoothing",
            quality_score=0.15
        )

        assert len(result.predictions) == 3
        assert result.method == "exp_smoothing"


class TestForecasterSelection:
    """Test automatic forecaster selection based on data points."""

    def test_select_exp_smoothing_for_many_points(self):
        """Should select ExponentialSmoothing for 7+ data points."""
        from app.forecasting.algorithms import get_forecaster_for_data, ExponentialSmoothingForecaster

        forecaster = get_forecaster_for_data(30)
        assert isinstance(forecaster, ExponentialSmoothingForecaster)

    def test_select_moving_avg_for_few_points(self):
        """Should select MovingAverage for 3-6 data points."""
        from app.forecasting.algorithms import get_forecaster_for_data, MovingAverageForecaster

        forecaster = get_forecaster_for_data(5)
        assert isinstance(forecaster, MovingAverageForecaster)

    def test_select_linear_for_two_points(self):
        """Should select LinearRegression for 2 data points."""
        from app.forecasting.algorithms import get_forecaster_for_data, LinearRegressionForecaster

        forecaster = get_forecaster_for_data(2)
        assert isinstance(forecaster, LinearRegressionForecaster)

    def test_select_naive_for_one_point(self):
        """Should select Naive for 1 data point."""
        from app.forecasting.algorithms import get_forecaster_for_data, NaiveForecaster

        forecaster = get_forecaster_for_data(1)
        assert isinstance(forecaster, NaiveForecaster)


class TestExponentialSmoothingForecaster:
    """Test ExponentialSmoothing forecaster."""

    def test_min_data_points(self):
        """Should require at least 7 data points."""
        from app.forecasting.algorithms import ExponentialSmoothingForecaster

        forecaster = ExponentialSmoothingForecaster()
        assert forecaster.min_data_points == 7

    def test_forecast_output_shape(self):
        """Output should match requested horizon."""
        from app.forecasting.algorithms import ExponentialSmoothingForecaster

        forecaster = ExponentialSmoothingForecaster()
        data = np.array([10.0, 12.0, 11.0, 13.0, 14.0, 12.0, 15.0, 16.0, 14.0, 17.0])
        horizon = 7

        result = forecaster.forecast(data, horizon)

        assert len(result.predictions) == horizon
        assert len(result.lower_bounds) == horizon
        assert len(result.upper_bounds) == horizon

    def test_forecast_method_name(self):
        """Result should have correct method name."""
        from app.forecasting.algorithms import ExponentialSmoothingForecaster

        forecaster = ExponentialSmoothingForecaster()
        data = np.array([10.0, 12.0, 11.0, 13.0, 14.0, 12.0, 15.0])
        result = forecaster.forecast(data, 3)

        assert result.method == "exp_smoothing"

    def test_forecast_bounds_order(self):
        """Lower bound should be <= prediction <= upper bound."""
        from app.forecasting.algorithms import ExponentialSmoothingForecaster

        forecaster = ExponentialSmoothingForecaster()
        data = np.array([10.0, 12.0, 11.0, 13.0, 14.0, 12.0, 15.0, 16.0])
        result = forecaster.forecast(data, 5, confidence=0.95)

        for i in range(len(result.predictions)):
            assert result.lower_bounds[i] <= result.predictions[i]
            assert result.predictions[i] <= result.upper_bounds[i]


class TestMovingAverageForecaster:
    """Test MovingAverage forecaster."""

    def test_min_data_points(self):
        """Should require at least 3 data points."""
        from app.forecasting.algorithms import MovingAverageForecaster

        forecaster = MovingAverageForecaster()
        assert forecaster.min_data_points == 3

    def test_forecast_output_shape(self):
        """Output should match requested horizon."""
        from app.forecasting.algorithms import MovingAverageForecaster

        forecaster = MovingAverageForecaster()
        data = np.array([10.0, 12.0, 14.0, 13.0, 15.0])
        horizon = 7

        result = forecaster.forecast(data, horizon)

        assert len(result.predictions) == horizon

    def test_forecast_is_mean_based(self):
        """Predictions should be based on recent mean."""
        from app.forecasting.algorithms import MovingAverageForecaster

        forecaster = MovingAverageForecaster()
        data = np.array([10.0, 10.0, 10.0, 10.0, 10.0])  # Constant data
        result = forecaster.forecast(data, 3)

        # All predictions should be close to 10.0
        np.testing.assert_array_almost_equal(result.predictions, [10.0, 10.0, 10.0])

    def test_forecast_method_name(self):
        """Result should have correct method name."""
        from app.forecasting.algorithms import MovingAverageForecaster

        forecaster = MovingAverageForecaster()
        data = np.array([10.0, 12.0, 11.0])
        result = forecaster.forecast(data, 3)

        assert result.method == "moving_avg"


class TestLinearRegressionForecaster:
    """Test LinearRegression forecaster."""

    def test_min_data_points(self):
        """Should require at least 2 data points."""
        from app.forecasting.algorithms import LinearRegressionForecaster

        forecaster = LinearRegressionForecaster()
        assert forecaster.min_data_points == 2

    def test_forecast_with_trend(self):
        """Should capture linear trend."""
        from app.forecasting.algorithms import LinearRegressionForecaster

        forecaster = LinearRegressionForecaster()
        # Clear upward trend: 10, 20
        data = np.array([10.0, 20.0])
        result = forecaster.forecast(data, 3)

        # Predictions should continue the trend
        assert result.predictions[0] > 20.0  # Next should be ~30
        assert result.predictions[1] > result.predictions[0]

    def test_forecast_method_name(self):
        """Result should have correct method name."""
        from app.forecasting.algorithms import LinearRegressionForecaster

        forecaster = LinearRegressionForecaster()
        data = np.array([10.0, 20.0])
        result = forecaster.forecast(data, 3)

        assert result.method == "linear"


class TestNaiveForecaster:
    """Test Naive forecaster (last value)."""

    def test_min_data_points(self):
        """Should require at least 1 data point."""
        from app.forecasting.algorithms import NaiveForecaster

        forecaster = NaiveForecaster()
        assert forecaster.min_data_points == 1

    def test_forecast_repeats_last_value(self):
        """All predictions should equal last value."""
        from app.forecasting.algorithms import NaiveForecaster

        forecaster = NaiveForecaster()
        data = np.array([42.0])
        result = forecaster.forecast(data, 5)

        np.testing.assert_array_equal(result.predictions, [42.0] * 5)

    def test_forecast_wide_bounds(self):
        """Bounds should be wide due to uncertainty."""
        from app.forecasting.algorithms import NaiveForecaster

        forecaster = NaiveForecaster()
        data = np.array([100.0])
        result = forecaster.forecast(data, 3)

        # Lower bound should be significantly lower
        assert result.lower_bounds[0] < result.predictions[0] * 0.6
        # Upper bound should be significantly higher
        assert result.upper_bounds[0] > result.predictions[0] * 1.4

    def test_forecast_method_name(self):
        """Result should have correct method name."""
        from app.forecasting.algorithms import NaiveForecaster

        forecaster = NaiveForecaster()
        data = np.array([10.0])
        result = forecaster.forecast(data, 3)

        assert result.method == "naive"


class TestConfidenceIntervals:
    """Test confidence interval calculation."""

    def test_wider_confidence_means_wider_bounds(self):
        """95% confidence should have wider bounds than 80%."""
        from app.forecasting.algorithms import MovingAverageForecaster

        forecaster = MovingAverageForecaster()
        data = np.array([10.0, 12.0, 11.0, 13.0, 14.0])

        result_95 = forecaster.forecast(data, 3, confidence=0.95)
        result_80 = forecaster.forecast(data, 3, confidence=0.80)

        # 95% bounds should be wider
        width_95 = result_95.upper_bounds[0] - result_95.lower_bounds[0]
        width_80 = result_80.upper_bounds[0] - result_80.lower_bounds[0]
        assert width_95 > width_80

    def test_default_confidence_is_95(self):
        """Default confidence level should be 95%."""
        from app.forecasting.algorithms import MovingAverageForecaster

        forecaster = MovingAverageForecaster()
        data = np.array([10.0, 12.0, 11.0, 13.0, 14.0])

        result_default = forecaster.forecast(data, 3)
        result_95 = forecaster.forecast(data, 3, confidence=0.95)

        np.testing.assert_array_almost_equal(
            result_default.lower_bounds,
            result_95.lower_bounds
        )


class TestNonNegativeForecasts:
    """Test that forecasts handle non-negative constraints."""

    def test_lower_bound_non_negative(self):
        """Lower bounds should never be negative for cost data."""
        from app.forecasting.algorithms import MovingAverageForecaster

        forecaster = MovingAverageForecaster()
        # Low values that might produce negative bounds
        data = np.array([0.5, 0.3, 0.4, 0.2, 0.6])
        result = forecaster.forecast(data, 5)

        # All lower bounds should be >= 0
        assert np.all(result.lower_bounds >= 0)

    def test_predictions_non_negative(self):
        """Predictions should never be negative."""
        from app.forecasting.algorithms import LinearRegressionForecaster

        forecaster = LinearRegressionForecaster()
        # Downward trend that could produce negatives
        data = np.array([10.0, 5.0])
        result = forecaster.forecast(data, 10)

        # All predictions should be >= 0
        assert np.all(result.predictions >= 0)


class TestQualityScore:
    """Test quality score calculation (MAPE)."""

    def test_quality_score_returned(self):
        """Forecast should include quality score when calculable."""
        from app.forecasting.algorithms import ExponentialSmoothingForecaster

        forecaster = ExponentialSmoothingForecaster()
        data = np.array([10.0, 12.0, 11.0, 13.0, 14.0, 12.0, 15.0, 16.0, 14.0, 17.0])
        result = forecaster.forecast(data, 3)

        # Quality score should be set (MAPE calculation)
        assert result.quality_score is not None
        assert 0 <= result.quality_score <= 1.0  # MAPE as fraction


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_zero_horizon_raises_error(self):
        """Horizon of 0 should raise error."""
        from app.forecasting.algorithms import MovingAverageForecaster

        forecaster = MovingAverageForecaster()
        data = np.array([10.0, 12.0, 11.0])

        with pytest.raises(ValueError):
            forecaster.forecast(data, 0)

    def test_empty_data_raises_error(self):
        """Empty data should raise error."""
        from app.forecasting.algorithms import NaiveForecaster

        forecaster = NaiveForecaster()
        data = np.array([])

        with pytest.raises(ValueError):
            forecaster.forecast(data, 3)

    def test_constant_data_handling(self):
        """Should handle constant data (zero variance)."""
        from app.forecasting.algorithms import MovingAverageForecaster

        forecaster = MovingAverageForecaster()
        data = np.array([5.0, 5.0, 5.0, 5.0, 5.0])
        result = forecaster.forecast(data, 3)

        # Should still produce valid result
        np.testing.assert_array_almost_equal(result.predictions, [5.0, 5.0, 5.0])
        # Bounds might be tight but should still exist
        assert len(result.lower_bounds) == 3
        assert len(result.upper_bounds) == 3
