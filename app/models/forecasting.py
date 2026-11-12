"""
Pydantic models for Cost Forecasting ML.

Defines forecasts, anomalies, and budget projections.
"""

from datetime import date, datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator


class ForecastHorizon(StrEnum):
    """Standard forecast horizons."""

    WEEK = "7"
    MONTH = "30"
    QUARTER = "90"


class ForecastMethod(StrEnum):
    """Forecasting algorithms available."""

    EXP_SMOOTHING = "exp_smoothing"
    MOVING_AVG = "moving_avg"
    LINEAR = "linear"
    NAIVE = "naive"
    ENSEMBLE = "ensemble"


class AnomalySeverity(StrEnum):
    """Severity levels for detected anomalies."""

    LOW = "low"  # z > 2
    MEDIUM = "medium"  # z > 2.5
    HIGH = "high"  # z > 3
    CRITICAL = "critical"  # z > 4


class ForecastRequest(BaseModel):
    """Request for cost forecast."""

    horizon_days: int = Field(default=7, ge=1, le=90)
    provider: str | None = None
    include_confidence: bool = True


class DailyForecast(BaseModel):
    """Single day forecast with confidence bounds."""

    date: date
    predicted_cost: float = Field(..., ge=0)
    lower_bound: float = Field(..., ge=0)
    upper_bound: float = Field(..., ge=0)

    @model_validator(mode="after")
    def validate_bounds(self) -> Self:
        """Ensure bounds are in correct order."""
        if self.lower_bound > self.predicted_cost:
            raise ValueError("lower_bound must be <= predicted_cost")
        if self.upper_bound < self.predicted_cost:
            raise ValueError("upper_bound must be >= predicted_cost")
        return self


class ForecastResponse(BaseModel):
    """Response containing forecast results."""

    user_id: str
    generated_at: datetime
    horizon_days: int
    method_used: ForecastMethod
    data_points_used: int
    total_predicted_cost: float
    daily_forecasts: list[DailyForecast]
    confidence_level: float = Field(default=0.95, ge=0, le=1)
    model_quality_score: float | None = None  # MAPE
    provider: str | None = None

    @model_validator(mode="after")
    def validate_daily_count(self) -> Self:
        """Ensure daily forecasts match horizon."""
        if len(self.daily_forecasts) != self.horizon_days:
            raise ValueError(
                f"daily_forecasts count ({len(self.daily_forecasts)}) "
                f"must match horizon_days ({self.horizon_days})"
            )
        return self


class AnomalyDetectionRequest(BaseModel):
    """Request for anomaly detection."""

    lookback_days: int = Field(default=30, ge=7, le=365)
    sensitivity: float = Field(default=2.0, ge=1.5, le=4.0)


class AnomalyResponse(BaseModel):
    """A detected cost anomaly."""

    id: str
    anomaly_date: date
    actual_cost: float
    expected_cost: float
    deviation_percent: float
    z_score: float
    severity: AnomalySeverity
    provider: str | None = None
    acknowledged: bool = False


class AnomalyListResponse(BaseModel):
    """List of detected anomalies."""

    anomalies: list[AnomalyResponse]
    total_count: int
    unacknowledged_count: int


class BudgetExhaustionResponse(BaseModel):
    """Budget exhaustion projection."""

    user_id: str
    monthly_budget: float
    current_spend: float
    percentage_used: float
    daily_burn_rate: float
    projected_exhaustion_date: date | None = None
    days_until_exhaustion: int | None = None
    confidence_percentage: float
    warning_level: Literal["safe", "caution", "warning", "critical"]
    recommendation: str


class ForecastSummaryResponse(BaseModel):
    """Comprehensive forecast summary."""

    aggregate: ForecastResponse
    by_provider: list[ForecastResponse] = Field(default_factory=list)
    budget_projection: BudgetExhaustionResponse
    recent_anomalies: list[AnomalyResponse] = Field(default_factory=list)
