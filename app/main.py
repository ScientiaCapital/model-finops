"""FastAPI service for AI Cost Optimizer."""
import asyncio
import os
import logging
import sqlite3
from typing import Optional, List
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from .providers import init_providers
from app.services.routing_service import RoutingService
from app.auth import get_current_user_id, OptionalAuth
from app.models.feedback import FeedbackRequest as ProductionFeedbackRequest, FeedbackResponse as ProductionFeedbackResponse
from app.database.feedback_store import FeedbackStore
from app.models.admin import (
    FeedbackSummary, LearningStatus,
    RetrainingResult, PerformanceTrends
)
from app.learning.feedback_trainer import FeedbackTrainer
from app.services.admin_service import get_admin_service
from app.scheduler import RetrainingScheduler
from app.cache import create_redis_cache
from app.routers import experiments
from app.experiments.tracker import ExperimentTracker

# Monetization imports
from app.routers import api_keys, billing, enterprise

# New feature imports (Sprint Dec 27)
from app.routers import arbitrage, forecasting, status, subscriptions
from app.routers.api_keys import init_api_key_service
from app.routers.billing import init_billing_router
from app.middleware import APIKeyMiddleware, QuotaEnforcementMiddleware
from app.billing import StripeClient
from app.services.billing_service import BillingService

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize retraining scheduler (before lifespan)
scheduler = None

if os.getenv('ENABLE_SCHEDULER', 'true').lower() == 'true':
    scheduler = RetrainingScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    # Startup
    logger.info("🚀 Starting AI Cost Optimizer with Supabase + Semantic Caching...")

    # Initialize Supabase client (singleton)
    from app.database import get_supabase_client
    supabase_client = get_supabase_client()
    app.state.supabase_client = supabase_client  # Store for middleware access
    logger.info("✅ Supabase client initialized")

    # Warm up embedding generator (load ML model)
    try:
        from app.embeddings import get_embedding_generator
        embeddings = get_embedding_generator()
        embeddings.warmup()  # Pre-load model to avoid cold start
        dim = embeddings.get_embedding_dimension()
        logger.info(f"✅ Embedding model loaded (dim={dim})")
    except Exception as e:
        logger.warning(f"⚠️ Embedding model not available: {e}")
        logger.warning("Semantic caching disabled - falling back to exact match")

    # Start scheduler
    if scheduler:
        scheduler.start()
        logger.info("✅ Retraining scheduler started")

    # Initialize admin service with scheduler (for next_scheduled_run info)
    from app.services.admin_service import get_admin_service
    get_admin_service(scheduler=scheduler)
    logger.info("✅ Admin service initialized")

    # Initialize monetization services (API keys and billing)
    stripe_api_key = os.getenv("STRIPE_SECRET_KEY")
    stripe_webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    if stripe_api_key:
        # Initialize Stripe client
        stripe_client = StripeClient(
            api_key=stripe_api_key,
            webhook_secret=stripe_webhook_secret,
        )
        logger.info("✅ Stripe client initialized")

        # Initialize billing service
        billing_service = BillingService(
            stripe_client=stripe_client,
            supabase_client=supabase_client,
        )
        logger.info("✅ Billing service initialized")

        # Initialize routers with services
        init_api_key_service(supabase_client)
        init_billing_router(billing_service, stripe_client, supabase_client)
        logger.info("✅ Monetization routers initialized (API keys + Billing)")

        # Store billing_service for middleware access
        app.state.billing_service = billing_service
    else:
        logger.warning("⚠️ STRIPE_SECRET_KEY not configured - billing disabled")
        app.state.billing_service = None

        # Still initialize API key service without Stripe
        init_api_key_service(supabase_client)
        logger.info("✅ API key service initialized (billing disabled)")

    logger.info("🎉 AI Cost Optimizer ready!")

    yield

    # Shutdown
    logger.info("🛑 Shutting down AI Cost Optimizer...")

    # Stop scheduler
    if scheduler:
        scheduler.stop()
        logger.info("✅ Retraining scheduler stopped")

    # Close Supabase client
    from app.database import close_supabase_client
    await close_supabase_client()
    logger.info("✅ Supabase client closed")

    # Release embedding model from memory
    from app.embeddings import close_embedding_generator
    close_embedding_generator()
    logger.info("✅ Embedding model released")

    logger.info("👋 Shutdown complete")


# Initialize FastAPI app
app = FastAPI(
    title="AI Cost Optimizer",
    description="Smart multi-LLM routing for cost optimization",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware (configurable via environment)
cors_origins = os.getenv("CORS_ORIGINS", "*")
# Parse comma-separated origins or use "*" for all
if cors_origins == "*":
    allow_origins = ["*"]
else:
    allow_origins = [origin.strip() for origin in cors_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add monetization middleware (lazy loading - services initialized in lifespan)
# Note: Middleware is added in reverse order (last added = first executed)
# Order: CORS → QuotaEnforcement → APIKeyAuth → Request Handler

# Quota enforcement (blocks when monthly token limit exceeded)
app.add_middleware(
    QuotaEnforcementMiddleware,
    protected_paths=["/chat", "/complete", "/v1/"],
    exclude_paths=["/health", "/docs", "/redoc", "/openapi.json", "/billing", "/api-keys"],
)

# API key authentication (validates X-API-Key header, enforces rate limits)
app.add_middleware(
    APIKeyMiddleware,
    protected_paths=["/v1/"],  # Only /v1/ prefix requires API key
    exclude_paths=["/health", "/docs", "/redoc", "/openapi.json", "/billing/webhook"],
)

# Include routers
app.include_router(experiments.router)
app.include_router(api_keys.router)
app.include_router(billing.router)
app.include_router(enterprise.router)

# Sprint Dec 27 feature routers
app.include_router(arbitrage.router)
app.include_router(forecasting.router)
app.include_router(status.router)

# Sprint Dec 29 feature routers
app.include_router(subscriptions.router)

# Initialize global components
providers = init_providers()
routing_service = RoutingService(
    providers=providers,
    user_id=None,  # Admin mode (no RLS filtering) for backward compatibility
    db_path=os.getenv("DATABASE_PATH", "optimizer.db")  # Legacy parameter
)
experiment_tracker = ExperimentTracker(db_path=os.getenv("DATABASE_PATH", "optimizer.db"))
feedback_store = FeedbackStore()
feedback_trainer = FeedbackTrainer()

# Initialize Redis cache for metrics endpoint (Task 4)
metrics_cache = create_redis_cache()

# Cache hit/miss statistics for monitoring (with thread-safe lock)
metrics_cache_stats = {
    "hits": 0,
    "misses": 0,
    "errors": 0
}
metrics_cache_stats_lock = asyncio.Lock()

logger.info(f"AI Cost Optimizer initialized with providers: {list(providers.keys())}")
logger.info(f"Metrics cache initialized: Redis available = {metrics_cache.ping()}")


# ============================================================================
# REAL-TIME METRICS (via Supabase Realtime)
# ============================================================================
#
# Custom WebSocket endpoint has been replaced with Supabase Realtime.
# Frontend clients should use Supabase Realtime subscriptions instead.
# See docs/REALTIME_SETUP.md for migration guide.


# Request/Response models
class CompleteRequest(BaseModel):
    """Request model for completion endpoint."""
    prompt: str = Field(..., min_length=1, description="User prompt")
    max_tokens: Optional[int] = Field(1000, ge=1, le=4000, description="Maximum response tokens")
    auto_route: bool = Field(False, description="Enable intelligent routing (hybrid strategy)")
    provider: Optional[str] = Field(None, description="Force specific provider (cerebras, openrouter, groq, together)")
    tokenizer_id: Optional[str] = Field(None, description="Optional HF repo id for tokenization metrics (e.g., 'UW/OLMo2-8B-SuperBPE-t180k')")
    user_id: Optional[str] = Field(None, description="User ID for A/B testing experiments")


class CompleteResponse(BaseModel):
    """Response model for completion endpoint."""
    request_id: str     # NEW: Unique request ID for feedback tracking
    response: str
    provider: str
    model: str
    strategy_used: str  # NEW: "complexity", "learning", "hybrid", "cached"
    confidence: str     # NEW: "high", "medium", "low"
    complexity: str     # DEPRECATED but kept for compatibility
    complexity_metadata: dict
    routing_metadata: dict  # NEW: Full RoutingDecision.metadata
    tokens_in: int
    tokens_out: int
    cost: float
    total_cost_today: float
    cache_hit: bool = False
    original_cost: Optional[float] = None
    savings: float = 0.0
    cache_key: Optional[str] = None
    tokenizer_id: Optional[str] = None
    tokenizer_tokens_in: Optional[int] = None
    tokenizer_bytes_per_token: Optional[float] = None
    tokenizer_tokens_per_byte: Optional[float] = None
    # A/B Testing Experiment Fields
    experiment_id: Optional[int] = None
    assigned_strategy: Optional[str] = None


class StatsResponse(BaseModel):
    """Response model for stats endpoint."""
    overall: dict
    by_provider: list
    by_complexity: list
    recent_requests: list


class FeedbackRequest(BaseModel):
    """Request model for feedback endpoint."""
    cache_key: str = Field(..., min_length=1, description="Cache key of response to rate")
    rating: int = Field(..., ge=-1, le=1, description="1 for upvote, -1 for downvote")
    comment: Optional[str] = Field(None, max_length=500, description="Optional feedback comment")


class FeedbackResponse(BaseModel):
    """Response model for feedback endpoint."""
    success: bool
    cache_key: str
    quality_score: Optional[float]
    invalidated: bool
    message: str


# API Endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "providers_available": list(routing_service.providers.keys()),
        "routing_engine": "v2",  # Phase 2 Auto-Routing with RoutingEngine
        "auto_route_enabled": routing_service.engine.track_metrics,
        "version": "2.0.0"  # Phase 2 FastAPI Integration
    }


@app.post("/complete", response_model=CompleteResponse)
async def complete_prompt(
    request: CompleteRequest,
    user_id: Optional[str] = Depends(OptionalAuth())
):
    """
    Route and complete a prompt using optimal provider with caching.
    NOW WITH A/B TESTING INTEGRATION.

    This is the main endpoint that:
    1. Checks for active A/B experiments (if user_id provided)
    2. Assigns user to control/test group and overrides routing strategy
    3. Checks response cache for instant results
    4. Routes using RoutingEngine (complexity or hybrid based on auto_route)
    5. Executes completion with selected provider
    6. Stores response in cache
    7. Records experiment result (if in experiment)
    8. Tracks cost and routing metrics
    9. Invalidates metrics cache on new data

    Args:
        request: CompleteRequest with prompt, max_tokens, auto_route, and optional user_id

    Returns:
        CompleteResponse with response text, metadata, cost, and experiment info

    Raises:
        HTTPException: If routing or completion fails
    """
    # A/B Testing Integration: Initialize experiment variables
    experiment_id = None
    assigned_strategy = None
    original_auto_route = request.auto_route  # Save original for logging

    # 1. Check for active experiments if user_id provided
    if request.user_id:
        try:
            active_experiments = experiment_tracker.get_active_experiments()

            if active_experiments:
                # Use first active experiment
                experiment = active_experiments[0]
                experiment_id = experiment['id']

                # 2. Assign user to control/test group (deterministic)
                assigned_strategy = experiment_tracker.assign_user(experiment_id, request.user_id)

                # 3. Override auto_route based on assigned strategy
                # Map experiment strategy to routing configuration
                strategy_map = {
                    'complexity': False,   # Complexity-based routing (auto_route=False)
                    'learning': True,      # Learning-based routing (auto_route=True)
                    'hybrid': True         # Hybrid routing (auto_route=True)
                }
                request.auto_route = strategy_map.get(assigned_strategy, request.auto_route)

                logger.info(
                    f"A/B Test: User {request.user_id} assigned to '{assigned_strategy}' "
                    f"(experiment {experiment_id}). Routing: auto_route={request.auto_route}"
                )
        except Exception as e:
            logger.error(f"Experiment assignment failed: {e}", exc_info=True)
            # Continue with normal routing if experiment fails
            experiment_id = None
            assigned_strategy = None

    try:
        # Execute routing with potentially overridden auto_route
        result = await routing_service.route_and_complete(
            prompt=request.prompt,
            auto_route=request.auto_route,
            max_tokens=request.max_tokens,
            provider_override=request.provider
        )

        # 4. Record experiment result if in experiment
        if experiment_id and request.user_id and assigned_strategy:
            try:
                # Extract latency from routing metadata
                latency_ms = result.get("routing_metadata", {}).get("latency_ms", 0.0)

                experiment_tracker.record_result(
                    experiment_id=experiment_id,
                    user_id=request.user_id,
                    strategy_assigned=assigned_strategy,
                    latency_ms=latency_ms,
                    cost_usd=result["cost"],
                    quality_score=None,  # Will be updated via feedback API
                    provider=result["provider"],
                    model=result["model"]
                )

                logger.info(
                    f"A/B Test: Recorded result for user {request.user_id} "
                    f"(experiment {experiment_id}, strategy '{assigned_strategy}')"
                )
            except Exception as e:
                logger.error(f"Failed to record experiment result: {e}", exc_info=True)
                # Don't fail the request if recording fails

        # Invalidate metrics cache when new routing decision is made
        # This ensures fresh metrics on next /routing/metrics call
        try:
            metrics_cache.delete("metrics:latest")
            logger.debug("Metrics cache invalidated after new routing decision")
        except Exception as e:
            logger.error(f"Metrics cache invalidation failed: {e}")

        # Optional tokenizer metrics
        tokenizer_id = request.tokenizer_id
        tokenizer_tokens_in = None
        tokenizer_bytes_per_token = None
        tokenizer_tokens_per_byte = None

        if tokenizer_id and not result["cache_hit"]:
            try:
                from .tokenizer_registry import estimate_tokenization_metrics
                est = estimate_tokenization_metrics(request.prompt, tokenizer_id)
                if est is not None:
                    tokenizer_tokens_in, tokenizer_bytes_per_token, tokenizer_tokens_per_byte = est
            except Exception as ex:
                logger.warning(f"Tokenizer metrics unavailable: {ex}")

        return CompleteResponse(
            request_id=result["request_id"],
            response=result["response"],
            provider=result["provider"],
            model=result["model"],
            strategy_used=result["strategy_used"],
            confidence=result["confidence"],
            complexity=result.get("strategy_used", "unknown"),  # Deprecated field
            complexity_metadata=result["complexity_metadata"],
            routing_metadata=result["routing_metadata"],
            tokens_in=result["tokens_in"],
            tokens_out=result["tokens_out"],
            cost=result["cost"],
            total_cost_today=result["total_cost_today"],
            cache_hit=result["cache_hit"],
            original_cost=result.get("original_cost"),
            savings=result.get("savings", 0.0),
            cache_key=result.get("cache_key"),
            tokenizer_id=tokenizer_id,
            tokenizer_tokens_in=tokenizer_tokens_in,
            tokenizer_bytes_per_token=tokenizer_bytes_per_token,
            tokenizer_tokens_per_byte=tokenizer_tokens_per_byte,
            # A/B Testing Experiment Fields
            experiment_id=experiment_id,
            assigned_strategy=assigned_strategy,
        )

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.get("/stats", response_model=StatsResponse)
async def get_usage_stats(
    user_id: Optional[str] = Depends(OptionalAuth())
):
    """
    Get usage statistics from database.

    Returns:
        Statistics including total costs, breakdowns by provider/complexity,
        and recent request history
    """
    try:
        stats = await routing_service.cost_tracker.get_usage_stats()
        return StatsResponse(**stats)

    except Exception as e:
        logger.error(f"Error fetching stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/providers")
async def list_providers():
    """
    List all available providers and their models.

    Returns:
        Dictionary of enabled providers with model information
    """
    return {
        "enabled_providers": list(providers.keys()),
        "models": {
            "gemini": {
                "name": "gemini-1.5-flash",
                "pricing": {"input_per_1m": "$0.075", "output_per_1m": "$0.30"},
                "recommended_for": "Simple queries, free tier available"
            },
            "claude": {
                "name": "claude-3-haiku-20240307",
                "pricing": {"input_per_1m": "$0.25", "output_per_1m": "$1.25"},
                "recommended_for": "Complex queries, best quality/cost balance"
            },
            "openrouter": {
                "name": "multiple models",
                "pricing": {"input_per_1m": "Varies", "output_per_1m": "Varies"},
                "recommended_for": "Fallback aggregator for all models"
            }
        }
    }


@app.get("/recommendation")
async def get_recommendation(
    prompt: str,
    user_id: Optional[str] = Depends(OptionalAuth())
):
    """
    Get routing recommendation without executing request.

    Always uses auto_route=true (hybrid strategy) for recommendations.
    Useful for previewing which model would be selected.

    Args:
        prompt: User prompt (query parameter)

    Returns:
        Routing information with provider, model, confidence, and reasoning
    """
    try:
        return routing_service.get_recommendation(prompt=prompt)

    except Exception as e:
        logger.error(f"Error getting recommendation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/routing/metrics")
async def get_routing_metrics(
    user_id: Optional[str] = Depends(OptionalAuth())
):
    """
    Get auto-routing analytics for monitoring and ROI tracking with Redis caching.

    Cache hierarchy:
    1. Redis (hot, <10ms) - 30-second TTL
    2. PostgreSQL/SQLite (warm, ~50ms) - query on cache miss

    Returns strategy performance, decision counts, and confidence distribution
    from the routing engine metrics collector.

    Returns:
        Dict with strategy_performance, total_decisions, confidence_distribution, provider_usage
    """
    cache_key = "metrics:latest"

    try:
        # Try Redis cache first
        cached_data = metrics_cache.get(cache_key)
        if cached_data:
            async with metrics_cache_stats_lock:
                metrics_cache_stats["hits"] += 1
            logger.info("Metrics cache HIT")
            return cached_data

        logger.info("Metrics cache MISS, querying database")
        async with metrics_cache_stats_lock:
            metrics_cache_stats["misses"] += 1

    except Exception as e:
        logger.warning(f"Cache GET failed: {e}, falling back to database")
        async with metrics_cache_stats_lock:
            metrics_cache_stats["errors"] += 1

    # Cache miss or error - query database
    try:
        db_metrics = await routing_service.get_routing_metrics(days=7)

        # Populate cache for next request (30-second TTL)
        try:
            metrics_cache.set(cache_key, db_metrics, ttl=30)
            logger.info("Metrics cached for 30 seconds")
        except Exception as e:
            logger.error(f"Cache SET failed: {e}")
            async with metrics_cache_stats_lock:
                metrics_cache_stats["errors"] += 1

        return db_metrics

    except Exception as e:
        logger.error(f"Error fetching routing metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/routing/decision")
async def get_routing_decision(
    prompt: str,
    auto_route: bool = True,
    user_id: Optional[str] = Depends(OptionalAuth())
):
    """
    Get detailed routing explanation for debugging and transparency.

    Returns complete RoutingDecision with all metadata for understanding
    why a particular provider/model was selected.

    Args:
        prompt: Prompt to analyze (query parameter)
        auto_route: Use intelligent routing (default: true)

    Returns:
        Dict with decision and full metadata
    """
    try:
        recommendation = routing_service.get_recommendation(prompt=prompt)

        return {
            "decision": {
                "provider": recommendation["provider"],
                "model": recommendation["model"],
                "confidence": recommendation["confidence"],
                "strategy_used": recommendation["strategy_used"],
                "reasoning": recommendation["reasoning"]
            },
            "metadata": recommendation["metadata"]
        }

    except Exception as e:
        logger.error(f"Error getting routing decision: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/cache/stats")
async def get_cache_stats(
    user_id: Optional[str] = Depends(OptionalAuth())
):
    """
    Get response cache statistics.

    Returns:
        Cache statistics including:
        - total_entries: Number of unique cached responses
        - total_hits: How many times cache was used
        - total_savings: Money saved from cache hits
        - hit_rate_percent: Cache hit rate percentage
        - popular_queries: Most frequently cached queries
    """
    try:
        stats = await routing_service.cost_tracker.get_cache_stats()
        return stats

    except Exception as e:
        logger.error(f"Error fetching cache stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics-cache/stats")
async def get_metrics_cache_stats(
    user_id: Optional[str] = Depends(OptionalAuth())
):
    """
    Get metrics cache performance statistics (Redis caching for /routing/metrics).

    This endpoint tracks the performance of the Redis cache layer added in Task 4
    to optimize the /routing/metrics endpoint from ~50ms to <10ms.

    Returns:
        Dict with:
        - hits: Number of cache hits
        - misses: Number of cache misses
        - errors: Number of cache errors (with fallback to DB)
        - hit_rate_percent: Cache hit rate percentage
        - total_requests: Total requests to metrics endpoint
        - redis_available: Whether Redis connection is healthy
    """
    # Capture stats snapshot while holding lock (minimal lock time)
    async with metrics_cache_stats_lock:
        total = metrics_cache_stats["hits"] + metrics_cache_stats["misses"]
        hit_rate = (metrics_cache_stats["hits"] / total * 100) if total > 0 else 0.0

        stats_snapshot = {
            "hits": metrics_cache_stats["hits"],
            "misses": metrics_cache_stats["misses"],
            "errors": metrics_cache_stats["errors"],
            "hit_rate_percent": round(hit_rate, 2),
            "total_requests": total,
        }

    # Perform I/O AFTER releasing lock in non-blocking manner
    loop = asyncio.get_event_loop()
    stats_snapshot["redis_available"] = await loop.run_in_executor(
        None, metrics_cache.ping
    )

    return stats_snapshot


@app.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest,
    user_agent: Optional[str] = None,
    user_id: Optional[str] = Depends(OptionalAuth())
):
    """
    Submit user feedback (thumbs up/down) for a cached response.

    This endpoint allows users to rate cached responses for quality.
    After 3+ votes, poor quality responses (score < 0.3) are automatically
    invalidated and will be regenerated on next request.

    Args:
        request: FeedbackRequest with cache_key, rating, and optional comment
        user_agent: Optional User-Agent header

    Returns:
        FeedbackResponse with updated quality score and invalidation status
    """
    try:
        # Add feedback to database
        routing_service.cost_tracker.add_feedback(
            cache_key=request.cache_key,
            rating=request.rating,
            comment=request.comment,
            user_agent=user_agent
        )

        # Update quality score (may trigger invalidation)
        quality_score = routing_service.cost_tracker.update_quality_score(request.cache_key)

        # Check if entry was invalidated
        conn = routing_service.cost_tracker._CostTracker__get_connection() if hasattr(routing_service.cost_tracker, '_CostTracker__get_connection') else None
        if not conn:
            conn = sqlite3.connect(routing_service.cost_tracker.db_path)

        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT invalidated FROM response_cache
            WHERE cache_key = ?
        """, (request.cache_key,))
        row = cursor.fetchone()
        invalidated = bool(row["invalidated"]) if row else False
        conn.close()

        logger.info(
            f"Feedback received: cache_key={request.cache_key[:16]}..., "
            f"rating={request.rating}, quality_score={quality_score}, invalidated={invalidated}"
        )

        message = "Thank you for your feedback!"
        if invalidated:
            message = "Response invalidated due to low quality. Future requests will generate a fresh response."
        elif quality_score is not None and quality_score < 0.5:
            message = "Thank you for your feedback! This response is being monitored for quality."

        return FeedbackResponse(
            success=True,
            cache_key=request.cache_key,
            quality_score=quality_score,
            invalidated=invalidated,
            message=message
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Error processing feedback: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/production/feedback", response_model=ProductionFeedbackResponse)
async def submit_production_feedback(
    request: ProductionFeedbackRequest,
    user_id: Optional[str] = Depends(OptionalAuth())
):
    """Submit quality feedback for a request.

    This endpoint collects user feedback on response quality for the
    production learning pipeline. Feedback is used to retrain routing
    recommendations.

    Args:
        request: Feedback submission with request_id, quality_score, correctness

    Returns:
        Feedback confirmation with feedback_id
    """
    try:
        admin_service = get_admin_service()
        feedback_id = await admin_service.store_routing_feedback(
            request_id=request.request_id,
            quality_score=request.quality_score,
            is_correct=request.is_correct,
            is_helpful=request.is_helpful,
            comment=request.comment,
            user_id=user_id
        )

        return ProductionFeedbackResponse(
            status="recorded",
            feedback_id=feedback_id,
            message="Thank you for feedback"
        )

    except Exception as e:
        logger.error(f"Failed to store production feedback: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to store feedback"
        )


@app.get("/quality/stats")
async def get_quality_stats(
    user_id: Optional[str] = Depends(OptionalAuth())
):
    """
    Get quality statistics across all cached responses.

    Returns quality metrics including:
    - overall: Aggregate quality stats
    - by_provider: Quality breakdown by provider
    - top_rated: Highest quality responses
    - worst_rated: Lowest quality responses (excluding invalidated)
    - invalidated_responses: Responses that were removed due to poor quality
    """
    try:
        stats = routing_service.cost_tracker.get_quality_stats()
        return stats

    except Exception as e:
        logger.error(f"Error fetching quality stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ANALYTICS DASHBOARD ENDPOINTS
# ============================================================================

@app.get("/analytics/cache")
async def get_cache_analytics(
    days: int = 7,
    user_id: Optional[str] = Depends(OptionalAuth())
):
    """
    Get comprehensive cache analytics for the cost optimization dashboard.

    This endpoint provides rich analytics on semantic cache performance,
    grouped by provider, to help understand cost savings and optimization
    effectiveness.

    Args:
        days: Number of days to look back (default: 7)

    Returns:
        Dict with:
        - summary: Overall cache performance metrics
        - by_provider: Per-provider breakdown with hit rates and quality
        - recommendations: AI-generated insights for optimization

    Example Response:
        {
            "summary": {
                "total_entries": 1250,
                "total_hits": 3800,
                "overall_hit_rate": 3.04,
                "avg_quality": 0.82,
                "estimated_savings_usd": 45.50
            },
            "by_provider": [
                {
                    "provider": "gemini",
                    "total_entries": 800,
                    "total_hits": 2500,
                    "avg_quality": 0.85,
                    "hit_rate": 3.12
                },
                {
                    "provider": "claude",
                    "total_entries": 450,
                    "total_hits": 1300,
                    "avg_quality": 0.78,
                    "hit_rate": 2.89
                }
            ],
            "recommendations": [
                "Consider routing more queries to Gemini - higher cache hit rate",
                "Claude responses have lower quality scores - review feedback"
            ]
        }
    """
    try:
        from app.database import get_supabase_client

        db = get_supabase_client()

        # Get per-provider analytics from Supabase
        provider_analytics = await db.get_cache_analytics(
            user_id=user_id,
            days_back=days
        )

        # Calculate summary metrics
        total_entries = sum(p.get('total_entries', 0) for p in provider_analytics)
        total_hits = sum(p.get('total_hits', 0) for p in provider_analytics)
        overall_hit_rate = (total_hits / total_entries) if total_entries > 0 else 0.0

        # Calculate weighted average quality
        weighted_quality_sum = sum(
            p.get('avg_quality', 0) * p.get('total_entries', 0)
            for p in provider_analytics
        )
        avg_quality = (weighted_quality_sum / total_entries) if total_entries > 0 else 0.0

        # Estimate savings (assume average $0.01 per cached response vs $0.02 for fresh)
        # This is a simplified estimation - actual savings depend on model pricing
        estimated_savings = total_hits * 0.012  # ~$0.012 saved per cache hit

        # Generate recommendations based on analytics
        recommendations = []

        if provider_analytics:
            # Find best and worst performing providers
            sorted_by_quality = sorted(
                [p for p in provider_analytics if p.get('total_entries', 0) > 10],
                key=lambda x: x.get('avg_quality', 0),
                reverse=True
            )

            if len(sorted_by_quality) >= 2:
                best = sorted_by_quality[0]
                worst = sorted_by_quality[-1]

                if best.get('avg_quality', 0) - worst.get('avg_quality', 0) > 0.15:
                    recommendations.append(
                        f"{best['provider'].title()} has significantly higher quality "
                        f"({best.get('avg_quality', 0):.2f} vs {worst.get('avg_quality', 0):.2f}) - "
                        f"consider routing more complex queries there"
                    )

            # Find providers with high hit rates
            high_hit_rate = [
                p for p in provider_analytics
                if p.get('hit_rate', 0) > 2.0 and p.get('total_entries', 0) > 20
            ]
            if high_hit_rate:
                best_cache = max(high_hit_rate, key=lambda x: x.get('hit_rate', 0))
                recommendations.append(
                    f"{best_cache['provider'].title()} has excellent cache reuse "
                    f"({best_cache.get('hit_rate', 0):.1f}x hit rate) - "
                    f"semantic caching is working well for this provider"
                )

            # Check for low quality providers
            low_quality = [
                p for p in provider_analytics
                if p.get('avg_quality', 0) < 0.5 and p.get('total_entries', 0) > 10
            ]
            for p in low_quality:
                recommendations.append(
                    f"{p['provider'].title()} has low quality scores "
                    f"({p.get('avg_quality', 0):.2f}) - review user feedback"
                )

        if not recommendations:
            recommendations.append(
                "Cache performance is healthy. Continue monitoring for optimization opportunities."
            )

        return {
            "summary": {
                "total_entries": total_entries,
                "total_hits": total_hits,
                "overall_hit_rate": round(overall_hit_rate, 2),
                "avg_quality": round(avg_quality, 2),
                "estimated_savings_usd": round(estimated_savings, 2),
                "days_analyzed": days
            },
            "by_provider": provider_analytics,
            "recommendations": recommendations
        }

    except Exception as e:
        logger.error(f"Error fetching cache analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/costs")
async def get_cost_analytics(
    days: int = 7,
    user_id: Optional[str] = Depends(OptionalAuth())
):
    """
    Get comprehensive cost analytics for the optimization dashboard.

    This endpoint aggregates cost data across providers, models, and
    complexity levels to provide insights into spending patterns and
    optimization opportunities.

    Args:
        days: Number of days to look back (default: 7)

    Returns:
        Dict with:
        - summary: Total costs, savings, and efficiency metrics
        - by_provider: Cost breakdown per provider
        - by_complexity: Cost breakdown per complexity level
        - by_day: Daily cost trends
        - optimization_score: Overall optimization effectiveness (0-100)

    Example Response:
        {
            "summary": {
                "total_cost_usd": 125.50,
                "total_requests": 5000,
                "avg_cost_per_request": 0.0251,
                "cache_savings_usd": 45.50,
                "effective_cost_reduction_percent": 26.6
            },
            "by_provider": [...],
            "by_complexity": [...],
            "optimization_score": 78
        }
    """
    try:
        # Get usage stats from cost tracker
        stats = await routing_service.cost_tracker.get_usage_stats()

        # Get cache stats for savings calculation
        cache_stats = await routing_service.cost_tracker.get_cache_stats()

        overall = stats.get('overall', {})
        total_cost = overall.get('total_cost', 0)
        total_requests = overall.get('total_requests', 0)

        # Calculate cache savings
        cache_hits = cache_stats.get('total_hits', 0)
        estimated_cache_savings = cache_hits * 0.012  # ~$0.012 saved per cache hit

        # Calculate effective cost reduction
        original_cost = total_cost + estimated_cache_savings
        cost_reduction_percent = (
            (estimated_cache_savings / original_cost * 100)
            if original_cost > 0 else 0
        )

        # Calculate optimization score (0-100)
        # Based on: cache hit rate, cost efficiency, and quality
        cache_entries = cache_stats.get('total_entries', 0)
        cache_hit_rate = (cache_hits / cache_entries) if cache_entries > 0 else 0
        quality_score = cache_stats.get('avg_quality_score', 0.5)

        optimization_score = min(100, int(
            (cache_hit_rate * 30) +  # Up to 30 points for cache efficiency
            (min(cost_reduction_percent, 50) * 1.0) +  # Up to 50 points for cost reduction
            (quality_score * 20)  # Up to 20 points for quality
        ))

        return {
            "summary": {
                "total_cost_usd": round(total_cost, 4),
                "total_requests": total_requests,
                "avg_cost_per_request": round(
                    total_cost / total_requests if total_requests > 0 else 0, 6
                ),
                "cache_savings_usd": round(estimated_cache_savings, 2),
                "effective_cost_reduction_percent": round(cost_reduction_percent, 1),
                "days_analyzed": days
            },
            "by_provider": stats.get('by_provider', []),
            "by_complexity": stats.get('by_complexity', []),
            "optimization_score": optimization_score,
            "optimization_breakdown": {
                "cache_efficiency_points": min(30, int(cache_hit_rate * 30)),
                "cost_reduction_points": min(50, int(cost_reduction_percent)),
                "quality_points": int(quality_score * 20),
                "max_possible": 100
            }
        }

    except Exception as e:
        logger.error(f"Error fetching cost analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/insights")
async def get_learning_insights(
    user_id: Optional[str] = Depends(OptionalAuth())
):
    """Get intelligent routing insights from learning module.

    NOTE: This endpoint is being migrated to the new routing architecture.
    Use /routing/metrics for current routing analytics.
    """
    return {
        "learning_active": False,
        "message": "This endpoint is deprecated. Please use /routing/metrics instead.",
        "migration_note": "Learning insights are being integrated into the new routing engine.",
        "alternative_endpoint": "/routing/metrics"
    }


# ============================================================================
# PROVIDER USAGE TRACKING (Work vs Personal Accounts)
# ============================================================================

@app.get("/analytics/provider-usage")
async def get_provider_usage(
    days: int = 30,
    user_id: Optional[str] = Depends(OptionalAuth())
):
    """
    Get usage data from all configured provider accounts.

    Supports multiple accounts per provider (work vs personal):
    - ANTHROPIC_API_KEY_WORK / ANTHROPIC_API_KEY_PERSONAL
    - OPENROUTER_API_KEY_WORK / OPENROUTER_API_KEY_PERSONAL

    Returns:
        - configured_accounts: Which providers/accounts are set up
        - balances: Current credit balances (OpenRouter)
        - usage_history: Historical usage from provider billing APIs
        - errors: Any API errors encountered

    Example Response:
        {
            "configured_accounts": {
                "anthropic": ["default", "work"],
                "openrouter": ["default", "personal"]
            },
            "balances": [
                {"provider": "openrouter", "account_label": "default", "balance_usd": 5.50}
            ],
            "usage_history": [
                {"provider": "anthropic", "account_label": "work", "date": "2024-12-25", "cost_usd": 12.50}
            ]
        }
    """
    from app.services.provider_usage import get_all_provider_usage

    try:
        result = await get_all_provider_usage(days=days)
        return result
    except Exception as e:
        logger.error(f"Error fetching provider usage: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================

def _is_sqlite(conn) -> bool:
    """Check if connection is SQLite."""
    return hasattr(conn, 'row_factory')


@app.get("/admin/feedback/summary", response_model=FeedbackSummary)
async def get_feedback_summary(
    current_user_id: Optional[str] = Depends(OptionalAuth())
):
    """Get feedback statistics summary."""
    admin_service = get_admin_service()
    result = await admin_service.get_feedback_summary(user_id=current_user_id)

    return FeedbackSummary(
        total_feedback=result['total_feedback'],
        avg_quality_score=result['avg_quality_score'],
        models=result['models']
    )


@app.get("/admin/learning/status", response_model=LearningStatus)
async def get_learning_status(
    current_user_id: Optional[str] = Depends(OptionalAuth())
):
    """Get learning pipeline status."""
    admin_service = get_admin_service()
    result = await admin_service.get_learning_status(user_id=current_user_id)

    return LearningStatus(
        last_retraining_run=result['last_retraining_run'],
        next_scheduled_run=result['next_scheduled_run'],
        confidence_distribution=result['confidence_distribution'],
        total_patterns=result['total_patterns']
    )


@app.post("/admin/learning/retrain", response_model=RetrainingResult)
async def trigger_retraining(
    dry_run: bool = True,
    current_user_id: Optional[str] = Depends(OptionalAuth())
):
    """Manually trigger retraining.

    Args:
        dry_run: If True, preview changes without applying

    Returns:
        Retraining result summary
    """
    if scheduler:
        result = scheduler.trigger_immediate_retraining(dry_run=dry_run)
    else:
        result = feedback_trainer.retrain(dry_run=dry_run)

    return RetrainingResult(**result)


@app.get("/admin/performance/trends", response_model=PerformanceTrends)
async def get_performance_trends(
    pattern: str,
    current_user_id: Optional[str] = Depends(OptionalAuth())
):
    """Get performance trends for a pattern.

    Args:
        pattern: Pattern to analyze (e.g., 'code', 'explanation')

    Returns:
        Performance trends over time
    """
    admin_service = get_admin_service()
    trends = await admin_service.get_performance_trends(pattern=pattern, user_id=current_user_id)

    return PerformanceTrends(
        pattern=pattern,
        trends=trends
    )


# ============================================================================
# BUDGET ALERTING ENDPOINTS
# ============================================================================

class BudgetConfigRequest(BaseModel):
    """Request model for budget configuration."""
    monthly_budget: float = Field(..., gt=0, description="Monthly budget in USD")
    alert_thresholds: Optional[List[float]] = Field(
        default=[0.5, 0.8, 0.9],
        description="Alert thresholds as percentages (0.0-1.0)"
    )
    alert_email: Optional[str] = Field(None, description="Email for alerts")
    alert_webhook_url: Optional[str] = Field(None, description="Custom webhook URL")
    slack_webhook_url: Optional[str] = Field(None, description="Slack webhook URL")
    discord_webhook_url: Optional[str] = Field(None, description="Discord webhook URL")
    alert_cooldown_minutes: int = Field(60, ge=1, description="Cooldown between alerts")


class BudgetConfigResponse(BaseModel):
    """Response model for budget configuration."""
    user_id: str
    monthly_budget: float
    alert_thresholds: List[float]
    alert_email: Optional[str]
    alert_webhook_url: Optional[str]
    slack_webhook_url: Optional[str]
    discord_webhook_url: Optional[str]
    alert_cooldown_minutes: int
    enabled: bool


class BudgetStatusResponse(BaseModel):
    """Response model for budget status."""
    user_id: str
    current_spend: float
    monthly_budget: float
    percentage_used: float
    remaining: float
    days_in_month: int
    days_remaining: int
    daily_average: float
    projected_monthly: float
    threshold_alerts: List[dict]
    status: str  # "healthy", "warning", "critical"


@app.get("/budget/config", response_model=BudgetConfigResponse)
async def get_budget_config(
    current_user_id: str = Depends(get_current_user_id)
):
    """Get user's budget configuration."""
    from app.services.budget_alerting import get_budget_service

    service = get_budget_service()
    config = await service.get_budget_config(current_user_id)

    if not config:
        raise HTTPException(status_code=404, detail="No budget configuration found")

    return BudgetConfigResponse(
        user_id=config.user_id,
        monthly_budget=config.monthly_budget,
        alert_thresholds=config.alert_thresholds,
        alert_email=config.alert_email,
        alert_webhook_url=config.alert_webhook_url,
        slack_webhook_url=config.slack_webhook_url,
        discord_webhook_url=config.discord_webhook_url,
        alert_cooldown_minutes=config.alert_cooldown_minutes,
        enabled=config.enabled,
    )


@app.post("/budget/config", response_model=BudgetConfigResponse)
async def set_budget_config(
    request: BudgetConfigRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """Create or update budget configuration."""
    from app.services.budget_alerting import get_budget_service

    service = get_budget_service()
    config = await service.set_budget_config(
        user_id=current_user_id,
        monthly_budget=request.monthly_budget,
        alert_thresholds=request.alert_thresholds,
        alert_email=request.alert_email,
        alert_webhook_url=request.alert_webhook_url,
        slack_webhook_url=request.slack_webhook_url,
        discord_webhook_url=request.discord_webhook_url,
        alert_cooldown_minutes=request.alert_cooldown_minutes,
    )

    return BudgetConfigResponse(
        user_id=config.user_id,
        monthly_budget=config.monthly_budget,
        alert_thresholds=config.alert_thresholds,
        alert_email=config.alert_email,
        alert_webhook_url=config.alert_webhook_url,
        slack_webhook_url=config.slack_webhook_url,
        discord_webhook_url=config.discord_webhook_url,
        alert_cooldown_minutes=config.alert_cooldown_minutes,
        enabled=config.enabled,
    )


@app.get("/budget/status", response_model=BudgetStatusResponse)
async def get_budget_status(
    current_user_id: str = Depends(get_current_user_id)
):
    """Get current budget status with projections."""
    from app.services.budget_alerting import get_budget_service

    service = get_budget_service()
    status = await service.get_budget_status(current_user_id)

    if not status:
        raise HTTPException(status_code=404, detail="No budget configuration found")

    # Determine status level
    if status.percentage_used >= 90:
        level = "critical"
    elif status.percentage_used >= 80:
        level = "warning"
    else:
        level = "healthy"

    return BudgetStatusResponse(
        user_id=status.user_id,
        current_spend=status.current_spend,
        monthly_budget=status.monthly_budget,
        percentage_used=status.percentage_used,
        remaining=status.remaining,
        days_in_month=status.days_in_month,
        days_remaining=status.days_remaining,
        daily_average=status.daily_average,
        projected_monthly=status.projected_monthly,
        threshold_alerts=status.threshold_alerts,
        status=level,
    )


@app.get("/budget/alerts")
async def get_budget_alerts(
    limit: int = 50,
    current_user_id: str = Depends(get_current_user_id)
):
    """Get user's budget alert history."""
    from app.services.budget_alerting import get_budget_service

    service = get_budget_service()
    alerts = await service.get_alert_history(current_user_id, limit=limit)

    return {"alerts": alerts, "count": len(alerts)}


@app.post("/budget/test-webhook")
async def test_budget_webhook(
    current_user_id: str = Depends(get_current_user_id)
):
    """Send a test alert to configured webhooks."""
    from app.services.budget_alerting import get_budget_service

    service = get_budget_service()
    config = await service.get_budget_config(current_user_id)

    if not config:
        raise HTTPException(status_code=404, detail="No budget configuration found")

    # Send test alert at 50% threshold
    channels = await service._send_alert(config, 0.5, config.monthly_budget * 0.5)

    return {
        "success": True,
        "channels_notified": channels,
        "message": f"Test alert sent to {len(channels)} channel(s)"
    }


# ============================================================================
# WEBSOCKET ENDPOINTS
# ============================================================================
#
# DEPRECATED: get_latest_metrics_for_websocket and /ws/metrics endpoint
# have been replaced with Supabase Realtime.
#
# Clients should subscribe to Supabase Realtime channels instead:
#   supabase.channel('routing-metrics')
#     .on('postgres_changes', {...}, callback)
#     .subscribe()
#
# See docs/REALTIME_SETUP.md for implementation details.
# ============================================================================


# Run the application
if __name__ == "__main__":
    import uvicorn

    # Check if any providers are available
    if not providers:
        logger.error(
            "No providers configured! Please set at least one API key:\n"
            "  - GOOGLE_API_KEY for Gemini\n"
            "  - ANTHROPIC_API_KEY for Claude\n"
            "  - OPENROUTER_API_KEY for OpenRouter"
        )
        exit(1)

    port = int(os.getenv("PORT", 8000))
    logger.info(f"Starting AI Cost Optimizer on port {port}")

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level=os.getenv("LOG_LEVEL", "info").lower()
    )
