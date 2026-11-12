"""Service layer for intelligent routing with async Supabase integration."""

import logging
import uuid
from typing import Any

from app.database import AsyncCostTracker
from app.providers import NoProvidersConfiguredError
from app.routing.engine import RoutingEngine
from app.routing.metrics_async import AsyncMetricsCollector
from app.routing.models import RoutingContext, RoutingDecision

logger = logging.getLogger(__name__)


class RoutingService:
    """FastAPI service layer for intelligent routing.

    Bridges FastAPI endpoints and RoutingEngine, handling:
    - Async cache integration with semantic search
    - Provider execution
    - Cost tracking with multi-tenancy
    - Response formatting
    - Metrics collection
    """

    def __init__(
        self,
        providers: dict[str, Any],
        user_id: str | None = None,
        db_path: str = "optimizer.db",  # Legacy, kept for backward compat
    ) -> None:
        """Initialize async routing service.

        Args:
            providers: Dictionary of initialized provider clients
            user_id: Optional user ID for RLS context (UUID string)
            db_path: Legacy parameter (kept for backward compatibility)
        """
        # NOTE: db_path kept for backward compatibility but now uses Supabase
        self.engine = RoutingEngine(db_path=db_path, track_metrics=True)
        self.providers = providers
        self.user_id = user_id

        # Initialize async services
        self.cost_tracker = AsyncCostTracker(user_id=user_id)
        self.metrics = AsyncMetricsCollector(user_id=user_id)

        logger.info(
            f"RoutingService initialized with {len(providers)} providers "
            f"(user_id={user_id}, async=True)"
        )

    async def route_and_complete(
        self,
        prompt: str,
        auto_route: bool,
        max_tokens: int,
        similarity_threshold: float = 0.95,
        provider_override: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Route prompt and execute completion with semantic cache check.

        Args:
            prompt: User prompt to route
            auto_route: If True, use intelligent hybrid routing
            max_tokens: Maximum response tokens
            similarity_threshold: Minimum similarity for semantic cache match (0.0-1.0)
            provider_override: Force specific provider (skip routing)
            user_id: Authenticated caller. The semantic cache is read and written only for
                this user; with None (anonymous) the cache is skipped entirely.

        Returns:
            Dict with response, provider, model, cost, and metadata
        """
        # Cache reads and writes are scoped to the caller so one user never receives another
        # user's cached response. Anonymous callers (user_id None) bypass the cache.
        cache_tracker = (
            self.cost_tracker if user_id == self.cost_tracker.user_id else AsyncCostTracker(user_id)
        )

        # Check cache first (SEMANTIC SEARCH! 🧠)
        cached = await cache_tracker.check_cache(
            prompt,
            max_tokens,
            similarity_threshold=similarity_threshold,
        )

        if cached:
            similarity = cached.get("similarity", 1.0)
            logger.info(
                f"✅ SEMANTIC Cache HIT! Similarity={similarity:.3f}, "
                f"Key: {cached['cache_key'][:16]}..."
            )

            # Record cache hit
            await cache_tracker.record_cache_hit(cached["cache_key"])

            # Log as request with $0 cost
            await self.cost_tracker.log_request(
                prompt=prompt,
                complexity=cached.get("complexity", "unknown"),
                provider="cache",
                model=cached["model"],
                tokens_in=0,
                tokens_out=0,
                cost=0.0,
            )

            total_cost = await self.cost_tracker.get_total_cost()

            # Generate unique request_id even for cached responses
            request_id = str(uuid.uuid4())

            return {
                "request_id": request_id,
                "response": cached["response"],
                "provider": cached["provider"],
                "model": cached["model"],
                "strategy_used": "cached",
                "confidence": "high",
                "complexity_metadata": {
                    "cached": True,
                    "original_timestamp": cached.get(
                        "created_at", cached.get("last_accessed", "unknown")
                    ),
                },
                "tokens_in": cached["tokens_in"],
                "tokens_out": cached["tokens_out"],
                "cost": 0.0,
                "total_cost_today": total_cost,
                "cache_hit": True,
                "original_cost": cached["cost"],
                "savings": cached["cost"],
                "cache_key": cached["cache_key"],
                "routing_metadata": {},
            }

        # Cache miss - proceed with routing
        logger.info("Cache MISS: routing to provider")

        # Generate unique request_id BEFORE routing for FK cascade
        request_id = str(uuid.uuid4())

        if not self.providers:
            raise NoProvidersConfiguredError()

        # Check for provider override (skip routing if specified)
        if provider_override:
            if provider_override not in self.providers:
                available = list(self.providers.keys())
                raise ValueError(
                    f"Provider '{provider_override}' not available. Available: {available}"
                )

            provider_name = provider_override
            provider = self.providers[provider_name]
            # Get model name from provider
            model_name = getattr(provider, "MODEL", "unknown")
            strategy_used = "override"
            confidence = "high"
            logger.info(f"Provider override: using {provider_name}/{model_name}")
        else:
            decision = self._decide(prompt, auto_route=auto_route, request_id=request_id)
            provider_name = decision.provider
            provider = self.providers[provider_name]
            model_name = decision.model

            strategy_used = decision.strategy_used
            confidence = decision.confidence

        # Call provider's complete() method - returns (text, input_tokens, output_tokens, cost)
        if provider_name == "openrouter":
            response_text, tokens_in, tokens_out, cost = await provider.complete(
                model=model_name, prompt=prompt, max_tokens=max_tokens
            )
        else:
            response_text, tokens_in, tokens_out, cost = await provider.complete(
                prompt=prompt, max_tokens=max_tokens
            )

        # Store in cache (with semantic embedding! ✨)
        try:
            await cache_tracker.store_in_cache(
                prompt=prompt,
                max_tokens=max_tokens,
                response=response_text,
                provider=provider_name,
                model=model_name,
                complexity="unknown",  # Will be set by engine in future
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost=cost,
            )
        except Exception as e:  # the cache is optional; the completion already succeeded
            logger.warning(f"cache write failed, response returned uncached: {e}")

        # Log to database
        await self.cost_tracker.log_request(
            prompt=prompt,
            complexity="unknown",
            provider=provider_name,
            model=model_name,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=cost,
        )

        total_cost = await self.cost_tracker.get_total_cost()

        # The key the cache row was stored under, so /feedback can find it
        normalized = " ".join(prompt.split())
        cache_key = cache_tracker.cache_key_for(normalized, max_tokens)

        # Build routing metadata
        routing_metadata = {}
        if not provider_override and "decision" in locals():
            routing_metadata = getattr(decision, "metadata", {})

        return {
            "request_id": request_id,
            "response": response_text,
            "provider": provider_name,
            "model": model_name,
            "strategy_used": strategy_used,
            "confidence": confidence,
            "complexity_metadata": routing_metadata,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost": cost,
            "total_cost_today": total_cost,
            "cache_hit": False,
            "original_cost": None,
            "savings": 0.0,
            "cache_key": cache_key,
            "routing_metadata": routing_metadata,
        }

    def get_recommendation(self, prompt: str) -> dict[str, Any]:
        """Get routing recommendation without execution.

        Args:
            prompt: User prompt to analyze

        Returns:
            Dict with provider, model, strategy, confidence, metadata
        """
        if not self.providers:
            raise NoProvidersConfiguredError()

        # Get routing decision using hybrid strategy
        decision = self._decide(prompt, auto_route=True)

        return {
            "provider": decision.provider,
            "model": decision.model,
            "strategy_used": decision.strategy_used,
            "confidence": decision.confidence,
            "reasoning": decision.reasoning,
            "metadata": decision.metadata,
        }

    def _decide(
        self, prompt: str, auto_route: bool, request_id: str | None = None
    ) -> RoutingDecision:
        """Route among the configured providers only.

        The candidate set is ``self.providers`` (what init_providers found configured), so a
        decision never names a provider that cannot serve the request. Callers must check that
        at least one provider is configured first.
        """
        context = RoutingContext(prompt=prompt, available_providers=list(self.providers))
        decision = self.engine.route(
            prompt=prompt, auto_route=auto_route, context=context, request_id=request_id
        )

        if decision.provider not in self.providers:
            # Defensive: a strategy ignored the candidate set. Re-route on complexity, which
            # always picks from context.available_providers.
            logger.warning(
                f"Routed provider '{decision.provider}' is not configured; "
                "re-routing among configured providers"
            )
            decision = self.engine.strategies["complexity"].route(prompt, context)
            decision.fallback_used = True

        if decision.model == "default":
            # The strategies have no model table for this provider; report the one it calls.
            decision.model = getattr(self.providers[decision.provider], "MODEL", decision.model)

        return decision

    async def get_routing_metrics(self, days: int = 7) -> dict[str, Any]:
        """Get routing performance metrics from Supabase.

        Args:
            days: Number of days to analyze (default: 7)

        Returns:
            Dict with strategy performance, decision counts, confidence distribution, cost savings
        """
        return await self.metrics.get_metrics(days=days)

    def set_user_context(self, user_id: str) -> None:
        """
        Set user context for RLS-protected operations.

        Args:
            user_id: User ID (UUID string)
        """
        self.user_id = user_id
        self.cost_tracker.set_user_context(user_id)
        self.metrics.set_user_context(user_id)
        logger.debug(f"User context set to {user_id} for all services")
