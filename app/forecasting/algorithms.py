"""
Forecasting algorithms for cost prediction.

Implements a hierarchy of forecasters based on available data:
- ExponentialSmoothing: 7+ data points (high confidence)
- MovingAverage: 3-6 data points (medium confidence)
- LinearRegression: 2 data points (low confidence)
- Naive: 1 data point (very low confidence)
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import numpy as np
from scipy import stats


@dataclass
class ForecastResult:
    """Result of a forecasting operation."""
    predictions: np.ndarray
    lower_bounds: np.ndarray
    upper_bounds: np.ndarray
    method: str
    quality_score: Optional[float] = None  # MAPE as fraction (0-1)


class BaseForecaster(ABC):
    """Abstract base class for forecasters."""

    @property
    @abstractmethod
    def min_data_points(self) -> int:
        """Minimum data points required for this forecaster."""
        pass

    @abstractmethod
    def forecast(
        self,
        data: np.ndarray,
        horizon: int,
        confidence: float = 0.95
    ) -> ForecastResult:
        """
        Generate forecast with confidence intervals.

        Args:
            data: Historical data points
            horizon: Number of periods to forecast
            confidence: Confidence level for intervals (0-1)

        Returns:
            ForecastResult with predictions and bounds
        """
        pass

    def _validate_inputs(self, data: np.ndarray, horizon: int):
        """Validate forecast inputs."""
        if len(data) == 0:
            raise ValueError("Data cannot be empty")
        if horizon <= 0:
            raise ValueError("Horizon must be positive")

    def _calculate_mape(self, actual: np.ndarray, predicted: np.ndarray) -> float:
        """Calculate Mean Absolute Percentage Error."""
        # Avoid division by zero
        mask = actual != 0
        if not mask.any():
            return 0.0
        mape = np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask]))
        return min(mape, 1.0)  # Cap at 100%

    def _ensure_non_negative(self, values: np.ndarray) -> np.ndarray:
        """Ensure all values are non-negative (for cost data)."""
        return np.maximum(values, 0.0)


class ExponentialSmoothingForecaster(BaseForecaster):
    """
    Exponential smoothing forecaster (Holt's method).

    Best for data with 7+ points. Captures level and trend.
    """

    @property
    def min_data_points(self) -> int:
        return 7

    def forecast(
        self,
        data: np.ndarray,
        horizon: int,
        confidence: float = 0.95
    ) -> ForecastResult:
        self._validate_inputs(data, horizon)

        # Simple exponential smoothing with trend (Holt's method)
        alpha = 0.3  # Level smoothing
        beta = 0.1   # Trend smoothing

        # Initialize
        level = data[0]
        trend = (data[-1] - data[0]) / len(data) if len(data) > 1 else 0

        # Fit model
        fitted = []
        for i, val in enumerate(data):
            if i == 0:
                fitted.append(level)
                continue
            prev_level = level
            level = alpha * val + (1 - alpha) * (level + trend)
            trend = beta * (level - prev_level) + (1 - beta) * trend
            fitted.append(level)

        # Generate predictions
        predictions = np.array([level + (i + 1) * trend for i in range(horizon)])
        predictions = self._ensure_non_negative(predictions)

        # Calculate residual standard error for intervals
        fitted_arr = np.array(fitted)
        residuals = data - fitted_arr
        std_error = np.std(residuals) if len(residuals) > 1 else np.std(data)

        # Z-score for confidence interval
        z = stats.norm.ppf((1 + confidence) / 2)

        # Prediction intervals widen with horizon
        interval_widths = z * std_error * np.sqrt(1 + np.arange(1, horizon + 1) * 0.1)

        lower_bounds = self._ensure_non_negative(predictions - interval_widths)
        upper_bounds = predictions + interval_widths

        # Quality score (in-sample MAPE)
        quality_score = self._calculate_mape(data, fitted_arr)

        return ForecastResult(
            predictions=predictions,
            lower_bounds=lower_bounds,
            upper_bounds=upper_bounds,
            method="exp_smoothing",
            quality_score=quality_score
        )


class MovingAverageForecaster(BaseForecaster):
    """
    Moving average forecaster.

    Good for 3-6 data points. Simple and robust.
    """

    def __init__(self, window: int = 3):
        self.window = window

    @property
    def min_data_points(self) -> int:
        return 3

    def forecast(
        self,
        data: np.ndarray,
        horizon: int,
        confidence: float = 0.95
    ) -> ForecastResult:
        self._validate_inputs(data, horizon)

        # Use available window size
        window = min(self.window, len(data))

        # Calculate moving average
        recent = data[-window:]
        avg = np.mean(recent)
        std = np.std(data) if len(data) > 1 else avg * 0.1

        # Handle zero variance case
        if std == 0:
            std = avg * 0.05 if avg > 0 else 0.01

        # All predictions are the same (flat forecast)
        predictions = np.full(horizon, avg)
        predictions = self._ensure_non_negative(predictions)

        # Confidence intervals
        z = stats.norm.ppf((1 + confidence) / 2)
        margin = z * std / np.sqrt(window)

        # Intervals widen slightly with horizon
        widening = 1 + np.arange(horizon) * 0.05
        lower_bounds = self._ensure_non_negative(predictions - margin * widening)
        upper_bounds = predictions + margin * widening

        return ForecastResult(
            predictions=predictions,
            lower_bounds=lower_bounds,
            upper_bounds=upper_bounds,
            method="moving_avg",
            quality_score=None  # No in-sample fit to evaluate
        )


class LinearRegressionForecaster(BaseForecaster):
    """
    Linear regression forecaster.

    Captures trend from 2+ data points.
    """

    @property
    def min_data_points(self) -> int:
        return 2

    def forecast(
        self,
        data: np.ndarray,
        horizon: int,
        confidence: float = 0.95
    ) -> ForecastResult:
        self._validate_inputs(data, horizon)

        # Fit linear regression
        n = len(data)
        x = np.arange(n)
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, data)

        # Generate predictions
        future_x = np.arange(n, n + horizon)
        predictions = intercept + slope * future_x
        predictions = self._ensure_non_negative(predictions)

        # Residual standard error
        fitted = intercept + slope * x
        residuals = data - fitted
        mse = np.mean(residuals ** 2) if n > 2 else (std_err ** 2)
        rmse = np.sqrt(mse) if mse > 0 else np.std(data)

        # Prediction intervals
        z = stats.norm.ppf((1 + confidence) / 2)
        x_mean = np.mean(x)
        x_var = np.var(x) if n > 1 else 1

        # Standard error of prediction
        se_pred = rmse * np.sqrt(1 + 1/n + (future_x - x_mean)**2 / (n * x_var + 0.001))
        margin = z * se_pred

        lower_bounds = self._ensure_non_negative(predictions - margin)
        upper_bounds = predictions + margin

        return ForecastResult(
            predictions=predictions,
            lower_bounds=lower_bounds,
            upper_bounds=upper_bounds,
            method="linear",
            quality_score=None
        )


class NaiveForecaster(BaseForecaster):
    """
    Naive forecaster (last value persistence).

    Fallback for 1 data point. High uncertainty.
    """

    @property
    def min_data_points(self) -> int:
        return 1

    def forecast(
        self,
        data: np.ndarray,
        horizon: int,
        confidence: float = 0.95
    ) -> ForecastResult:
        self._validate_inputs(data, horizon)

        # Last value as prediction
        last_value = data[-1]
        predictions = np.full(horizon, last_value)

        # Wide uncertainty bounds (50% of value)
        uncertainty = last_value * 0.5 if last_value > 0 else 1.0

        # Bounds widen with horizon
        widening = 1 + np.arange(horizon) * 0.1
        lower_bounds = self._ensure_non_negative(predictions - uncertainty * widening)
        upper_bounds = predictions + uncertainty * widening

        return ForecastResult(
            predictions=predictions,
            lower_bounds=lower_bounds,
            upper_bounds=upper_bounds,
            method="naive",
            quality_score=None
        )


def get_forecaster_for_data(n_points: int) -> BaseForecaster:
    """
    Select appropriate forecaster based on data availability.

    Args:
        n_points: Number of available data points

    Returns:
        Best forecaster for the data size
    """
    if n_points >= 7:
        return ExponentialSmoothingForecaster()
    elif n_points >= 3:
        return MovingAverageForecaster()
    elif n_points >= 2:
        return LinearRegressionForecaster()
    else:
        return NaiveForecaster()
