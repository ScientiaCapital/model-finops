"""
Forecasting Service - Business logic for cost prediction and anomaly detection.

Provides methods to forecast costs, detect anomalies, and project budget exhaustion.
"""
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
from uuid import uuid4
import numpy as np

from app.models.forecasting import (
    ForecastRequest,
    ForecastResponse,
    DailyForecast,
    ForecastMethod,
    AnomalyDetectionRequest,
    AnomalyResponse,
    AnomalyListResponse,
    AnomalySeverity,
    BudgetExhaustionResponse,
    ForecastSummaryResponse,
)
from app.forecasting.algorithms import (
    get_forecaster_for_data,
    ForecastResult,
)

logger = logging.getLogger(__name__)


class ForecastingService:
    """
    Service for cost forecasting and anomaly detection.

    Uses lightweight ML algorithms with graceful degradation
    based on available data.
    """

    def __init__(self, supabase_client=None):
        """
        Initialize forecasting service.

        Args:
            supabase_client: Optional Supabase client for data access
        """
        self.supabase = supabase_client
        self._default_confidence = 0.95
        self._anomaly_sensitivity = 2.0  # Z-score threshold

    async def generate_forecast(
        self,
        user_id: str,
        request: ForecastRequest,
    ) -> ForecastResponse:
        """
        Generate cost forecast for a user.

        Args:
            user_id: User ID
            request: Forecast parameters

        Returns:
            ForecastResponse with predictions and bounds
        """
        # Get historical data
        historical_data = await self._get_historical_costs(
            user_id,
            provider=request.provider,
            days=max(30, request.horizon_days * 2),
        )

        if not historical_data:
            # No data - return naive forecast
            return self._create_empty_forecast(user_id, request)

        # Convert to numpy array
        costs = np.array([d["total_cost"] for d in historical_data])

        # Select appropriate forecaster
        forecaster = get_forecaster_for_data(len(costs))

        # Generate forecast
        confidence = self._default_confidence if request.include_confidence else 0.5
        result = forecaster.forecast(
            costs,
            request.horizon_days,
            confidence=confidence,
        )

        # Build response
        daily_forecasts = self._build_daily_forecasts(
            result,
            request.horizon_days,
        )

        return ForecastResponse(
            user_id=user_id,
            generated_at=datetime.utcnow(),
            horizon_days=request.horizon_days,
            method_used=ForecastMethod(result.method),
            data_points_used=len(costs),
            total_predicted_cost=float(np.sum(result.predictions)),
            daily_forecasts=daily_forecasts,
            confidence_level=confidence,
            model_quality_score=result.quality_score,
            provider=request.provider,
        )

    async def detect_anomalies(
        self,
        user_id: str,
        request: AnomalyDetectionRequest,
    ) -> AnomalyListResponse:
        """
        Detect cost anomalies for a user.

        Args:
            user_id: User ID
            request: Detection parameters

        Returns:
            AnomalyListResponse with detected anomalies
        """
        # Get historical data
        historical_data = await self._get_historical_costs(
            user_id,
            days=request.lookback_days,
        )

        if len(historical_data) < 7:
            # Not enough data for anomaly detection
            return AnomalyListResponse(
                anomalies=[],
                total_count=0,
                unacknowledged_count=0,
            )

        # Calculate statistics
        costs = np.array([d["total_cost"] for d in historical_data])
        dates = [d["cost_date"] for d in historical_data]
        mean_cost = np.mean(costs)
        std_cost = np.std(costs)

        if std_cost == 0:
            # No variance - no anomalies
            return AnomalyListResponse(
                anomalies=[],
                total_count=0,
                unacknowledged_count=0,
            )

        # Detect anomalies using Z-score
        anomalies = []
        for i, (cost, cost_date) in enumerate(zip(costs, dates)):
            z_score = (cost - mean_cost) / std_cost

            if abs(z_score) > request.sensitivity:
                severity = self._z_score_to_severity(abs(z_score))
                deviation = ((cost - mean_cost) / mean_cost) * 100

                anomaly = AnomalyResponse(
                    id=str(uuid4()),
                    anomaly_date=cost_date if isinstance(cost_date, date) else date.fromisoformat(cost_date),
                    actual_cost=float(cost),
                    expected_cost=float(mean_cost),
                    deviation_percent=float(deviation),
                    z_score=float(z_score),
                    severity=severity,
                    acknowledged=False,
                )
                anomalies.append(anomaly)

        # Sort by date (most recent first)
        anomalies.sort(key=lambda x: x.anomaly_date, reverse=True)

        # Get acknowledged count from DB
        unack_count = sum(1 for a in anomalies if not a.acknowledged)

        return AnomalyListResponse(
            anomalies=anomalies,
            total_count=len(anomalies),
            unacknowledged_count=unack_count,
        )

    async def project_budget_exhaustion(
        self,
        user_id: str,
        monthly_budget: float,
    ) -> BudgetExhaustionResponse:
        """
        Project when budget will be exhausted.

        Args:
            user_id: User ID
            monthly_budget: Monthly budget limit

        Returns:
            BudgetExhaustionResponse with projection
        """
        # Get current month spend
        today = date.today()
        month_start = today.replace(day=1)
        days_in_month = 30  # Approximate

        historical_data = await self._get_historical_costs(
            user_id,
            days=(today - month_start).days + 1,
        )

        if not historical_data:
            return BudgetExhaustionResponse(
                user_id=user_id,
                monthly_budget=monthly_budget,
                current_spend=0.0,
                percentage_used=0.0,
                daily_burn_rate=0.0,
                projected_exhaustion_date=None,
                days_until_exhaustion=None,
                confidence_percentage=0.0,
                warning_level="safe",
                recommendation="No spending data available yet.",
            )

        current_spend = sum(d["total_cost"] for d in historical_data)
        days_elapsed = len(historical_data)
        daily_burn_rate = current_spend / days_elapsed if days_elapsed > 0 else 0

        percentage_used = (current_spend / monthly_budget) * 100 if monthly_budget > 0 else 0

        # Project exhaustion
        if daily_burn_rate > 0:
            remaining_budget = monthly_budget - current_spend
            days_until = int(remaining_budget / daily_burn_rate)
            exhaustion_date = today + timedelta(days=max(0, days_until))
        else:
            days_until = None
            exhaustion_date = None

        # Determine warning level
        warning_level, recommendation = self._get_budget_warning(
            percentage_used,
            days_until,
            days_in_month - days_elapsed,
        )

        # Confidence based on data points
        confidence = min(95.0, days_elapsed * 10)

        return BudgetExhaustionResponse(
            user_id=user_id,
            monthly_budget=monthly_budget,
            current_spend=current_spend,
            percentage_used=percentage_used,
            daily_burn_rate=daily_burn_rate,
            projected_exhaustion_date=exhaustion_date,
            days_until_exhaustion=days_until,
            confidence_percentage=confidence,
            warning_level=warning_level,
            recommendation=recommendation,
        )

    async def get_forecast_summary(
        self,
        user_id: str,
        monthly_budget: float,
    ) -> ForecastSummaryResponse:
        """
        Get comprehensive forecast summary.

        Args:
            user_id: User ID
            monthly_budget: Monthly budget limit

        Returns:
            ForecastSummaryResponse with all forecasting data
        """
        # Generate aggregate forecast
        aggregate = await self.generate_forecast(
            user_id,
            ForecastRequest(horizon_days=7),
        )

        # Get anomalies
        anomalies_response = await self.detect_anomalies(
            user_id,
            AnomalyDetectionRequest(lookback_days=30),
        )

        # Get budget projection
        budget = await self.project_budget_exhaustion(user_id, monthly_budget)

        return ForecastSummaryResponse(
            aggregate=aggregate,
            by_provider=[],  # TODO: Add per-provider forecasts
            budget_projection=budget,
            recent_anomalies=anomalies_response.anomalies[:5],  # Top 5
        )

    async def acknowledge_anomaly(
        self,
        user_id: str,
        anomaly_id: str,
        notes: Optional[str] = None,
    ) -> bool:
        """Acknowledge an anomaly."""
        if not self.supabase:
            return False

        try:
            await self.supabase.table("cost_anomalies") \
                .update({
                    "acknowledged": True,
                    "acknowledged_at": datetime.utcnow().isoformat(),
                    "acknowledged_by": user_id,
                    "notes": notes,
                }) \
                .eq("id", anomaly_id) \
                .eq("user_id", user_id) \
                .execute()
            return True
        except Exception as e:
            logger.error(f"Failed to acknowledge anomaly: {e}")
            return False

    async def _get_historical_costs(
        self,
        user_id: str,
        provider: Optional[str] = None,
        days: int = 30,
    ) -> List[Dict]:
        """Get historical cost data for forecasting."""
        if not self.supabase:
            # Return mock data for testing
            return self._generate_mock_data(days)

        try:
            query = self.supabase.table("daily_cost_aggregates") \
                .select("cost_date, total_cost, request_count") \
                .eq("user_id", user_id) \
                .gte("cost_date", (date.today() - timedelta(days=days)).isoformat()) \
                .order("cost_date", desc=False)

            if provider:
                query = query.eq("provider", provider)
            else:
                query = query.is_("provider", None)  # Aggregate only

            result = await query.execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to get historical costs: {e}")
            return []

    def _generate_mock_data(self, days: int) -> List[Dict]:
        """Generate mock data for testing without database."""
        base_cost = 10.0
        data = []
        for i in range(days):
            cost_date = date.today() - timedelta(days=days - i - 1)
            # Add some noise and trend
            noise = np.random.normal(0, 2)
            trend = i * 0.1
            cost = max(0, base_cost + noise + trend)
            data.append({
                "cost_date": cost_date.isoformat(),
                "total_cost": cost,
                "request_count": int(cost * 10),
            })
        return data

    def _build_daily_forecasts(
        self,
        result: ForecastResult,
        horizon: int,
    ) -> List[DailyForecast]:
        """Build daily forecast list from algorithm result."""
        forecasts = []
        today = date.today()

        for i in range(horizon):
            forecast_date = today + timedelta(days=i + 1)
            forecasts.append(DailyForecast(
                date=forecast_date,
                predicted_cost=float(result.predictions[i]),
                lower_bound=float(result.lower_bounds[i]),
                upper_bound=float(result.upper_bounds[i]),
            ))

        return forecasts

    def _create_empty_forecast(
        self,
        user_id: str,
        request: ForecastRequest,
    ) -> ForecastResponse:
        """Create forecast response when no data available."""
        today = date.today()
        daily_forecasts = [
            DailyForecast(
                date=today + timedelta(days=i + 1),
                predicted_cost=0.0,
                lower_bound=0.0,
                upper_bound=0.0,
            )
            for i in range(request.horizon_days)
        ]

        return ForecastResponse(
            user_id=user_id,
            generated_at=datetime.utcnow(),
            horizon_days=request.horizon_days,
            method_used=ForecastMethod.NAIVE,
            data_points_used=0,
            total_predicted_cost=0.0,
            daily_forecasts=daily_forecasts,
            confidence_level=0.0,
            model_quality_score=None,
            provider=request.provider,
        )

    def _z_score_to_severity(self, z: float) -> AnomalySeverity:
        """Convert Z-score to severity level."""
        if z >= 4.0:
            return AnomalySeverity.CRITICAL
        elif z >= 3.0:
            return AnomalySeverity.HIGH
        elif z >= 2.5:
            return AnomalySeverity.MEDIUM
        else:
            return AnomalySeverity.LOW

    def _get_budget_warning(
        self,
        percentage_used: float,
        days_until: Optional[int],
        days_remaining: int,
    ) -> tuple:
        """Determine budget warning level and recommendation.

        Priority order:
        1. Budget exhausted (100%+) - always critical
        2. Percentage thresholds (90%, 75%) - static limits
        3. Projection thresholds - dynamic based on burn rate
        """
        if percentage_used >= 100:
            return "critical", "Budget exhausted! Consider reducing usage or increasing budget."

        # Check percentage thresholds FIRST (static limits take priority)
        if percentage_used >= 90:
            return "critical", "Over 90% of budget used. Immediate action needed."
        if percentage_used >= 75:
            return "warning", "Budget 75% used. Consider optimizing usage."

        # Then check projection (dynamic burn rate)
        if days_until is not None and days_until < days_remaining:
            if days_until <= 3:
                return "critical", f"Budget will exhaust in {days_until} days at current rate."
            elif days_until <= 7:
                return "warning", f"Budget projected to exhaust in {days_until} days."
            elif days_until <= 14:
                return "caution", f"Budget may exhaust before month end ({days_until} days)."

        return "safe", "Budget on track for the month."
