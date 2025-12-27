"""
Forecasting REST API Router.

Provides endpoints for cost forecasting, anomaly detection, and budget projections.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user_id
from app.models.forecasting import (
    ForecastRequest,
    ForecastResponse,
    AnomalyDetectionRequest,
    AnomalyListResponse,
    BudgetExhaustionResponse,
    ForecastSummaryResponse,
)
from app.services.forecasting_service import ForecastingService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/forecasting",
    tags=["Forecasting"],
    responses={404: {"description": "Not found"}},
)


def get_forecasting_service() -> ForecastingService:
    """Dependency to get forecasting service instance."""
    # TODO: Inject Supabase client when available
    return ForecastingService()


@router.get("/predict", response_model=ForecastResponse)
async def get_forecast(
    horizon_days: int = Query(7, ge=1, le=90, description="Forecast horizon in days"),
    provider: Optional[str] = Query(None, description="Filter by provider"),
    include_confidence: bool = Query(True, description="Include confidence intervals"),
    user_id: str = Depends(get_current_user_id),
    service: ForecastingService = Depends(get_forecasting_service),
) -> ForecastResponse:
    """
    Generate cost forecast for the user.

    Uses the best available forecasting method based on data availability:
    - 7+ data points: Exponential Smoothing (high confidence)
    - 3-6 points: Moving Average (medium confidence)
    - 2 points: Linear Regression (low confidence)
    - 1 point: Naive/Last Value (very low confidence)

    Returns:
        ForecastResponse with daily predictions and confidence bounds
    """
    try:
        request = ForecastRequest(
            horizon_days=horizon_days,
            provider=provider,
            include_confidence=include_confidence,
        )
        response = await service.generate_forecast(user_id, request)
        return response
    except Exception as e:
        logger.error(f"Error generating forecast: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate forecast")


@router.get("/summary", response_model=ForecastSummaryResponse)
async def get_forecast_summary(
    monthly_budget: float = Query(..., gt=0, description="Monthly budget in USD"),
    user_id: str = Depends(get_current_user_id),
    service: ForecastingService = Depends(get_forecasting_service),
) -> ForecastSummaryResponse:
    """
    Get comprehensive forecast summary.

    Includes:
    - Aggregate 7-day forecast
    - Per-provider forecasts
    - Budget exhaustion projection
    - Recent anomalies

    Returns:
        ForecastSummaryResponse with complete forecasting data
    """
    try:
        response = await service.get_forecast_summary(user_id, monthly_budget)
        return response
    except Exception as e:
        logger.error(f"Error getting summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to get forecast summary")


@router.get("/anomalies", response_model=AnomalyListResponse)
async def get_anomalies(
    lookback_days: int = Query(30, ge=7, le=365, description="Days to look back"),
    sensitivity: float = Query(2.0, ge=1.5, le=4.0, description="Z-score threshold"),
    user_id: str = Depends(get_current_user_id),
    service: ForecastingService = Depends(get_forecasting_service),
) -> AnomalyListResponse:
    """
    Detect cost anomalies.

    Uses Z-score based detection:
    - sensitivity=2.0: More anomalies detected
    - sensitivity=3.0: Only significant anomalies
    - sensitivity=4.0: Only critical anomalies

    Returns:
        AnomalyListResponse with detected anomalies
    """
    try:
        request = AnomalyDetectionRequest(
            lookback_days=lookback_days,
            sensitivity=sensitivity,
        )
        response = await service.detect_anomalies(user_id, request)
        return response
    except Exception as e:
        logger.error(f"Error detecting anomalies: {e}")
        raise HTTPException(status_code=500, detail="Failed to detect anomalies")


@router.post("/anomalies/{anomaly_id}/acknowledge")
async def acknowledge_anomaly(
    anomaly_id: str,
    notes: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    service: ForecastingService = Depends(get_forecasting_service),
) -> dict:
    """
    Acknowledge an anomaly as reviewed.

    Args:
        anomaly_id: The anomaly ID to acknowledge
        notes: Optional notes about the anomaly

    Returns:
        Success status
    """
    try:
        success = await service.acknowledge_anomaly(user_id, anomaly_id, notes)
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Anomaly not found or already acknowledged",
            )
        return {"status": "acknowledged", "anomaly_id": anomaly_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error acknowledging anomaly: {e}")
        raise HTTPException(status_code=500, detail="Failed to acknowledge anomaly")


@router.get("/budget-exhaustion", response_model=BudgetExhaustionResponse)
async def get_budget_exhaustion(
    monthly_budget: float = Query(..., gt=0, description="Monthly budget in USD"),
    user_id: str = Depends(get_current_user_id),
    service: ForecastingService = Depends(get_forecasting_service),
) -> BudgetExhaustionResponse:
    """
    Get budget exhaustion projection.

    Calculates:
    - Current spend vs budget
    - Daily burn rate
    - Projected exhaustion date
    - Warning level and recommendations

    Returns:
        BudgetExhaustionResponse with projection details
    """
    try:
        response = await service.project_budget_exhaustion(user_id, monthly_budget)
        return response
    except Exception as e:
        logger.error(f"Error projecting budget: {e}")
        raise HTTPException(status_code=500, detail="Failed to project budget")


@router.get("/health")
async def forecasting_health() -> dict:
    """
    Health check for forecasting service.

    Returns service status and capabilities.
    """
    return {
        "status": "healthy",
        "service": "forecasting",
        "capabilities": {
            "forecast_methods": ["exp_smoothing", "moving_avg", "linear", "naive"],
            "max_horizon_days": 90,
            "anomaly_detection": True,
            "budget_projection": True,
        },
    }
