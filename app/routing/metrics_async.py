"""Async metrics collection for routing decisions with Supabase."""

import logging
from datetime import datetime, timedelta
from typing import Any

from app.database.supabase_client import get_supabase_client
from app.routing.models import RoutingDecision

logger = logging.getLogger(__name__)


class AsyncMetricsCollector:
    """
    Async metrics collector with Supabase backend and multi-tenancy.

    Tracks routing decisions, cost savings, quality scores, and
    confidence levels for monitoring and optimization.

    Key Features:
    - Async database operations
    - Multi-tenant RLS support
    - Time-based aggregations
    - ROI and cost savings calculations
    """

    def __init__(self, user_id: str | None = None) -> None:
        """
        Initialize async metrics collector.

        Args:
            user_id: Optional user ID for RLS context (UUID string)
                    If None, operates in admin mode (bypasses RLS)
        """
        self.user_id = user_id
        self.db = get_supabase_client()

        logger.info(f"AsyncMetricsCollector initialized (user_id={user_id})")

    def set_user_context(self, user_id: str) -> None:
        """
        Set user context for RLS.

        Args:
            user_id: User ID (UUID string)
        """
        self.user_id = user_id
        logger.debug(f"User context set to {user_id}")

    async def track_decision(
        self, prompt: str, decision: RoutingDecision, auto_route: bool, request_id: str = None
    ) -> dict[str, Any]:
        """
        Track a routing decision to the database.

        Args:
            prompt: The original prompt
            decision: The routing decision made
            auto_route: Whether auto_route was enabled
            request_id: Unique request identifier for FK relationships (optional)

        Returns:
            Inserted metrics row
        """
        prompt_preview = prompt[:100] + "..." if len(prompt) > 100 else prompt
        timestamp = datetime.now()

        # Extract metadata
        decision.metadata.get("complexity")
        decision.metadata.get("pattern")

        # Estimate cost
        estimated_cost = self._estimate_cost(decision.provider, decision.model)

        # Prepare data
        data = {
            "timestamp": timestamp.isoformat(),
            "prompt_preview": prompt_preview,
            "strategy_used": decision.strategy_used,
            "provider": decision.provider,
            "model": decision.model,
            "confidence": decision.confidence,
            "tokens_in": decision.metadata.get("tokens_in", 0),
            "tokens_out": decision.metadata.get("tokens_out", 0),
            "cost": estimated_cost,
            "cache_hit": False,  # Will be updated if cache is used
            "metadata": decision.metadata,  # JSONB column
            "request_id": request_id,
            "user_id": self.user_id,  # For RLS
        }

        use_admin = self.user_id is None

        result = await self.db.insert("routing_metrics", data, use_admin=use_admin)

        logger.debug(
            f"Tracked routing decision: {decision.provider}/{decision.model} "
            f"(request_id={request_id}, auto_route={auto_route})"
        )

        return result

    async def get_cost_savings(self, days: int = 7) -> dict[str, Any]:
        """
        Calculate cost savings from intelligent routing.

        Compares actual costs (auto_route=True) vs baseline costs
        (auto_route=False) to estimate savings.

        Args:
            days: Number of days to analyze

        Returns:
            Dict with total_saved, percent_saved, intelligent_cost, baseline_cost
        """
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

        filters = {}
        if self.user_id:
            filters["user_id"] = self.user_id

        use_admin = self.user_id is None

        # Fetch all metrics for the period
        metrics = await self.db.select(
            "routing_metrics", columns="cost,metadata", filters=filters, use_admin=use_admin
        )

        # Filter by timestamp (PostgreSQL timestamp comparison)
        metrics = [m for m in metrics if m.get("timestamp", "") >= cutoff_date]

        if not metrics:
            return {
                "total_saved": 0.0,
                "percent_saved": 0.0,
                "intelligent_cost": 0.0,
                "baseline_cost": 0.0,
                "period_days": days,
            }

        # Separate by auto_route setting (from metadata JSONB)
        intelligent_metrics = [m for m in metrics if m.get("metadata", {}).get("auto_route")]
        baseline_metrics = [m for m in metrics if not m.get("metadata", {}).get("auto_route")]

        intelligent_cost = sum(m.get("cost", 0.0) for m in intelligent_metrics)
        baseline_cost = sum(m.get("cost", 0.0) for m in baseline_metrics)

        # Calculate savings
        total_saved = baseline_cost - intelligent_cost
        percent_saved = (total_saved / baseline_cost * 100) if baseline_cost > 0 else 0.0

        return {
            "total_saved": total_saved,
            "percent_saved": percent_saved,
            "intelligent_cost": intelligent_cost,
            "baseline_cost": baseline_cost,
            "period_days": days,
            "intelligent_requests": len(intelligent_metrics),
            "baseline_requests": len(baseline_metrics),
        }

    async def aggregate_by_strategy(self, days: int = 7) -> list[dict[str, Any]]:
        """
        Aggregate metrics by strategy type.

        Args:
            days: Number of days to analyze

        Returns:
            List of dicts with strategy, count, avg_cost, avg_confidence
        """
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

        filters = {}
        if self.user_id:
            filters["user_id"] = self.user_id

        use_admin = self.user_id is None

        # Fetch all metrics for the period
        metrics = await self.db.select(
            "routing_metrics",
            columns="strategy_used,cost,confidence,timestamp",
            filters=filters,
            use_admin=use_admin,
        )

        # Filter by timestamp
        metrics = [m for m in metrics if m.get("timestamp", "") >= cutoff_date]

        if not metrics:
            return []

        # Group by strategy
        strategy_groups = {}
        for m in metrics:
            strategy = m.get("strategy_used", "unknown")
            if strategy not in strategy_groups:
                strategy_groups[strategy] = {"costs": [], "confidences": []}

            strategy_groups[strategy]["costs"].append(m.get("cost", 0.0))
            strategy_groups[strategy]["confidences"].append(m.get("confidence", "low"))

        # Calculate aggregates
        results = []
        for strategy, data in strategy_groups.items():
            count = len(data["costs"])
            avg_cost = sum(data["costs"]) / count if count > 0 else 0.0
            high_conf_count = sum(1 for c in data["confidences"] if c == "high")
            high_conf_pct = (high_conf_count / count * 100) if count > 0 else 0.0

            results.append(
                {
                    "strategy": strategy,
                    "count": count,
                    "avg_cost": avg_cost,
                    "high_confidence_pct": high_conf_pct,
                }
            )

        # Sort by count descending
        results.sort(key=lambda x: x["count"], reverse=True)

        return results

    async def aggregate_by_confidence(self, days: int = 7) -> list[dict[str, Any]]:
        """
        Aggregate metrics by confidence level.

        Args:
            days: Number of days to analyze

        Returns:
            List of dicts with confidence, count, avg_cost
        """
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

        filters = {}
        if self.user_id:
            filters["user_id"] = self.user_id

        use_admin = self.user_id is None

        # Fetch all metrics for the period
        metrics = await self.db.select(
            "routing_metrics",
            columns="confidence,cost,timestamp",
            filters=filters,
            use_admin=use_admin,
        )

        # Filter by timestamp
        metrics = [m for m in metrics if m.get("timestamp", "") >= cutoff_date]

        if not metrics:
            return []

        # Group by confidence
        conf_groups = {}
        for m in metrics:
            confidence = m.get("confidence", "unknown")
            if confidence not in conf_groups:
                conf_groups[confidence] = []

            conf_groups[confidence].append(m.get("cost", 0.0))

        # Calculate aggregates
        results = []
        for confidence, costs in conf_groups.items():
            count = len(costs)
            avg_cost = sum(costs) / count if count > 0 else 0.0

            results.append({"confidence": confidence, "count": count, "avg_cost": avg_cost})

        # Sort by count descending
        results.sort(key=lambda x: x["count"], reverse=True)

        return results

    async def get_metrics(self, days: int = 7) -> dict[str, Any]:
        """
        Get comprehensive routing metrics for analysis.

        This is the main metrics endpoint that aggregates all routing data
        for monitoring and ROI tracking.

        Args:
            days: Number of days to analyze (default: 7)

        Returns:
            Dict with strategy_performance, total_decisions, confidence_distribution,
            provider_usage, cost_savings
        """
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

        filters = {}
        if self.user_id:
            filters["user_id"] = self.user_id

        use_admin = self.user_id is None

        # Fetch all metrics for the period
        all_metrics = await self.db.select(
            "routing_metrics", columns="*", filters=filters, use_admin=use_admin
        )

        # Filter by timestamp
        metrics = [m for m in all_metrics if m.get("timestamp", "") >= cutoff_date]

        # Total decisions
        total_decisions = len(metrics)

        # Strategy performance
        strategy_perf = {}
        for strategy in await self.aggregate_by_strategy(days):
            strategy_perf[strategy["strategy"]] = {
                "count": strategy["count"],
                "avg_cost": round(strategy["avg_cost"], 6) if strategy["avg_cost"] else 0,
                "high_confidence_pct": round(strategy["high_confidence_pct"], 2),
            }

        # Confidence distribution
        conf_dist = {"high": 0, "medium": 0, "low": 0}
        for conf in await self.aggregate_by_confidence(days):
            conf_dist[conf["confidence"]] = conf["count"]

        # Provider usage
        provider_groups = {}
        for m in metrics:
            provider = m.get("provider", "unknown")
            if provider not in provider_groups:
                provider_groups[provider] = []
            provider_groups[provider].append(m.get("cost", 0.0))

        provider_usage = {}
        for provider, costs in provider_groups.items():
            count = len(costs)
            avg_cost = sum(costs) / count if count > 0 else 0.0
            provider_usage[provider] = {"count": count, "avg_cost": round(avg_cost, 6)}

        # Cost savings
        savings = await self.get_cost_savings(days)

        return {
            "total_decisions": total_decisions,
            "strategy_performance": strategy_perf,
            "confidence_distribution": conf_dist,
            "provider_usage": provider_usage,
            "cost_savings": savings,
            "period_days": days,
            "timestamp": datetime.now().isoformat(),
        }

    def _estimate_cost(self, provider: str, model: str) -> float:
        """
        Estimate cost for a provider/model combination.

        Simplified cost estimates based on typical pricing.

        Args:
            provider: Provider name
            model: Model name

        Returns:
            Estimated cost in USD per request (assuming ~1K tokens)
        """
        # Simplified cost estimates (per 1K tokens average)
        cost_map = {
            ("gemini", "gemini-1.5-flash"): 0.00012,
            ("gemini", "gemini-1.5-pro"): 0.00250,
            ("claude", "claude-3-haiku-20240307"): 0.00095,
            ("claude", "claude-3-5-sonnet-20241022"): 0.0030,
            ("claude", "claude-3-opus-20240229"): 0.0150,
            ("cerebras", "llama3.1-70b"): 0.00010,
            ("openrouter", "google/gemini-flash-1.5"): 0.00015,
            ("openrouter", "anthropic/claude-3-haiku"): 0.00100,
        }

        return cost_map.get((provider, model), 0.001)  # Default fallback
