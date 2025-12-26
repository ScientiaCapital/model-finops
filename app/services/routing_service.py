"""Service layer for intelligent routing with async Supabase integration."""
import hashlib
import logging
import uuid
from typing import Dict, Any, Optional

from app.routing.engine import RoutingEngine
from app.routing.models import RoutingContext
from app.database import AsyncCostTracker
from app.routing.metrics_async import AsyncMetricsCollector

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
        providers: Dict[str, Any],
        user_id: Optional[str] = None,
        db_path: str = "optimizer.db"  # Legacy, kept for backward compat
    ):
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
        provider_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """Route prompt and execute completion with semantic cache check.

        Args:
            prompt: User prompt to route
            auto_route: If True, use intelligent hybrid routing
            max_tokens: Maximum response tokens
            similarity_threshold: Minimum similarity for semantic cache match (0.0-1.0)
            provider_override: Force specific provider (skip routing)

        Returns:
            Dict with response, provider, model, cost, and metadata
        """
        # Check cache first (SEMANTIC SEARCH! 🧠)
        cached = await self.cost_tracker.check_cache(
            prompt,
            max_tokens,
            similarity_threshold=similarity_threshold
        )

        if cached:
            similarity = cached.get("similarity", 1.0)
            logger.info(
                f"✅ SEMANTIC Cache HIT! Similarity={similarity:.3f}, "
                f"Key: {cached['cache_key'][:16]}..."
            )

            # Record cache hit
            await self.cost_tracker.record_cache_hit(cached["cache_key"])

            # Log as request with $0 cost
            await self.cost_tracker.log_request(
                prompt=prompt,
                complexity=cached.get("complexity", "unknown"),
                provider="cache",
                model=cached["model"],
                tokens_in=0,
                tokens_out=0,
                cost=0.0
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
                    "original_timestamp": cached.get("created_at", cached.get("last_accessed", "unknown"))
                },
                "tokens_in": cached["tokens_in"],
                "tokens_out": cached["tokens_out"],
                "cost": 0.0,
                "total_cost_today": total_cost,
                "cache_hit": True,
                "original_cost": cached["cost"],
                "savings": cached["cost"],
                "cache_key": cached["cache_key"],
                "routing_metadata": {}
            }

        # Cache miss - proceed with routing
        logger.info("Cache MISS: routing to provider")

        # Generate unique request_id BEFORE routing for FK cascade
        request_id = str(uuid.uuid4())

        # Check for provider override (skip routing if specified)
        if provider_override:
            if provider_override not in self.providers:
                available = list(self.providers.keys())
                raise ValueError(f"Provider '{provider_override}' not available. Available: {available}")

            provider_name = provider_override
            provider = self.providers[provider_name]
            # Get model name from provider
            model_name = getattr(provider, 'MODEL', 'unknown')
            strategy_used = "override"
            confidence = "high"
            logger.info(f"Provider override: using {provider_name}/{model_name}")
        else:
            # Get routing decision from engine
            context = RoutingContext(prompt=prompt)
            decision = self.engine.route(prompt=prompt, auto_route=auto_route, context=context, request_id=request_id)

            # Check if routed provider is available
            if decision.provider not in self.providers:
                # Fallback to first available provider
                fallback = list(self.providers.keys())[0]
                logger.warning(f"Routed provider '{decision.provider}' not available, falling back to '{fallback}'")
                provider_name = fallback
                provider = self.providers[fallback]
                model_name = getattr(provider, 'MODEL', 'unknown')
            else:
                provider_name = decision.provider
                provider = self.providers[decision.provider]
                model_name = decision.model

            strategy_used = decision.strategy.value if hasattr(decision.strategy, 'value') else str(decision.strategy)
            confidence = decision.confidence.value if hasattr(decision.confidence, 'value') else str(decision.confidence)

        # Call provider's complete() method - returns (text, input_tokens, output_tokens, cost)
        if provider_name == "openrouter":
            response_text, tokens_in, tokens_out, cost = await provider.complete(
                model=model_name,
                prompt=prompt,
                max_tokens=max_tokens
            )
        else:
            response_text, tokens_in, tokens_out, cost = await provider.complete(
                prompt=prompt,
                max_tokens=max_tokens
            )

        # Store in cache (with semantic embedding! ✨)
        await self.cost_tracker.store_in_cache(
            prompt=prompt,
            max_tokens=max_tokens,
            response=response_text,
            provider=provider_name,
            model=model_name,
            complexity="unknown",  # Will be set by engine in future
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=cost
        )

        # Log to database
        await self.cost_tracker.log_request(
            prompt=prompt,
            complexity="unknown",
            provider=provider_name,
            model=model_name,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=cost
        )

        total_cost = await self.cost_tracker.get_total_cost()

        # Generate cache key directly (avoid private method access)
        normalized = " ".join(prompt.split())
        cache_key = hashlib.sha256(f"{normalized}|{max_tokens}".encode()).hexdigest()

        # Build routing metadata
        routing_metadata = {}
        if not provider_override and 'decision' in locals():
            routing_metadata = getattr(decision, 'metadata', {})

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
            "routing_metadata": routing_metadata
        }

    def get_recommendation(self, prompt: str) -> Dict[str, Any]:
        """Get routing recommendation without execution.

        Args:
            prompt: User prompt to analyze

        Returns:
            Dict with provider, model, strategy, confidence, metadata
        """
        # Get routing decision using hybrid strategy
        context = RoutingContext(prompt=prompt)
        decision = self.engine.route(prompt=prompt, auto_route=True, context=context)

        return {
            "provider": decision.provider,
            "model": decision.model,
            "strategy_used": decision.strategy_used,
            "confidence": decision.confidence,
            "reasoning": decision.reasoning,
            "metadata": decision.metadata
        }

    async def get_routing_metrics(self, days: int = 7) -> Dict[str, Any]:
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
