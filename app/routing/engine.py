"""Routing engine that orchestrates strategy selection and execution."""
import logging
from typing import Optional, Dict

from app.routing.models import RoutingDecision, RoutingContext
from app.routing.strategy import (
    RoutingStrategy,
    ComplexityStrategy,
    LearningStrategy,
    HybridStrategy
)
from app.routing.metrics import MetricsCollector

logger = logging.getLogger(__name__)


class RoutingEngine:
    """Orchestrates routing strategy selection and execution.

    The RoutingEngine is the main entry point for routing decisions.
    It manages strategy instances and delegates routing to the appropriate
    strategy based on configuration.

    Attributes:
        strategies: Dict mapping strategy names to instances
        db_path: Path to database for learning strategy
    """

    VALID_PROVIDERS = ['gemini', 'claude', 'openrouter', 'ollama', 'deepseek', 'glm', 'qwen']
    VALID_CONFIDENCE = ['high', 'medium', 'low']

    def __init__(self, db_path: str = "optimizer.db", track_metrics: bool = True):
        """Initialize routing engine.

        Args:
            db_path: Path to database for learning strategy
            track_metrics: Whether to track routing metrics (default: True)
        """
        self.db_path = db_path
        self.track_metrics = track_metrics

        # Initialize metrics collector
        if track_metrics:
            self.metrics = MetricsCollector(db_path=db_path)
        else:
            self.metrics = None

        # Initialize all available strategies
        self.strategies: Dict[str, RoutingStrategy] = {
            "complexity": ComplexityStrategy(),
            "learning": LearningStrategy(db_path=db_path),
            "hybrid": HybridStrategy(db_path=db_path)
        }

        logger.info("RoutingEngine initialized")

    def route(
        self,
        prompt: str,
        auto_route: bool = False,
        context: Optional[RoutingContext] = None,
        request_id: str = None
    ) -> RoutingDecision:
        """Route a prompt to the optimal provider/model.

        Args:
            prompt: The user prompt to route
            auto_route: If True, use intelligent hybrid routing (learning + complexity).
                       If False, use simple complexity-based routing (default, safe).
            context: Optional routing context with constraints
            request_id: Unique request identifier for FK relationships (optional)

        Returns:
            RoutingDecision with provider, model, and metadata
        """
        # Select strategy based on auto_route flag
        strategy_name = "hybrid" if auto_route else "complexity"
        selected_strategy = self.strategies[strategy_name]

        # Create default context if none provided
        if context is None:
            context = RoutingContext(prompt=prompt)

        logger.info(f"Routing with auto_route={auto_route} (strategy={strategy_name})")

        # Execute routing with validation and fallback
        try:
            decision = selected_strategy.route(prompt, context)

            # Validate decision
            if not self._is_valid_decision(decision):
                raise ValueError(f"Invalid routing decision: provider={decision.provider}, model={decision.model}")

            logger.info(
                f"Routed to {decision.provider}/{decision.model} "
                f"(confidence={decision.confidence}, strategy={decision.strategy_used})"
            )

            # Track metrics if enabled
            if self.metrics:
                self.metrics.track_decision(prompt, decision, auto_route, request_id)

            return decision

        except Exception as e:
            logger.error(f"Routing failed with {strategy_name}: {e}")

            # Fallback to complexity strategy
            logger.info("Falling back to complexity strategy")
            fallback_decision = self.strategies['complexity'].route(prompt, context)
            fallback_decision.fallback_used = True
            fallback_decision.metadata['fallback_reason'] = str(e)

            # Track metrics for fallback if enabled
            if self.metrics:
                self.metrics.track_decision(prompt, fallback_decision, auto_route, request_id)

            return fallback_decision

    def _is_valid_decision(self, decision: RoutingDecision) -> bool:
        """Validate routing decision has valid provider, model, and confidence.

        Args:
            decision: Routing decision to validate

        Returns:
            True if decision is valid, False otherwise
        """
        return (
            decision.provider in self.VALID_PROVIDERS and
            decision.confidence in self.VALID_CONFIDENCE and
            decision.model is not None and
            len(decision.model) > 0
        )
