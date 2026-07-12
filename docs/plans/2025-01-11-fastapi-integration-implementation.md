# FastAPI Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrate Phase 2 Auto-Routing (RoutingEngine + MetricsCollector) into FastAPI application with clean three-layer architecture.

**Architecture:** Create RoutingService layer to bridge FastAPI and RoutingEngine. Replace legacy Router with RoutingEngine. Add auto_route parameter for intelligent routing. Preserve backward compatibility with auto_route=false default.

**Tech Stack:** FastAPI, Pydantic, RoutingEngine (Phase 2), MetricsCollector (Phase 2), CostTracker (existing)

---

## Task 1: Create RoutingService Foundation

**Files:**

- Create: `app/services/__init__.py`
- Create: `app/services/routing_service.py`
- Create: `tests/test_routing_service.py`

**Step 1: Create services package**

```bash
mkdir -p app/services
touch app/services/__init__.py
```

**Step 2: Write failing test for RoutingService initialization**

File: `tests/test_routing_service.py`

```python
"""Tests for RoutingService."""
import pytest
from app.services.routing_service import RoutingService


@pytest.fixture
def providers():
    """Mock providers dictionary."""
    return {
        "gemini": {"name": "gemini-1.5-flash"},
        "claude": {"name": "claude-3-haiku-20240307"}
    }


def test_routing_service_initialization(providers, tmp_path):
    """Test that RoutingService initializes correctly."""
    db_path = str(tmp_path / "test.db")

    service = RoutingService(db_path=db_path, providers=providers)

    assert service.engine is not None
    assert service.providers == providers
    assert service.cost_tracker is not None
```

**Step 3: Run test to verify it fails**

Run: `pytest tests/test_routing_service.py::test_routing_service_initialization -v`

Expected: FAIL with "No module named 'app.services.routing_service'"

**Step 4: Write minimal RoutingService implementation**

File: `app/services/routing_service.py`

```python
"""Service layer for intelligent routing."""
import logging
from typing import Dict, Any

from app.routing.engine import RoutingEngine
from app.routing.models import RoutingContext
from app.database import CostTracker

logger = logging.getLogger(__name__)


class RoutingService:
    """FastAPI service layer for intelligent routing.

    Bridges FastAPI endpoints and RoutingEngine, handling:
    - Cache integration
    - Provider execution
    - Cost tracking
    - Response formatting
    """

    def __init__(self, db_path: str, providers: Dict[str, Any]):
        """Initialize routing service.

        Args:
            db_path: Path to SQLite database
            providers: Dictionary of initialized provider clients
        """
        self.engine = RoutingEngine(db_path=db_path, track_metrics=True)
        self.providers = providers
        self.cost_tracker = CostTracker(db_path=db_path)

        logger.info(f"RoutingService initialized with {len(providers)} providers")
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_routing_service.py::test_routing_service_initialization -v`

Expected: PASS

**Step 6: Commit**

```bash
git add app/services/ tests/test_routing_service.py
git commit -m "feat: create RoutingService foundation with initialization"
```

---

## Task 2: Implement route_and_complete Method (TDD)

**Files:**

- Modify: `app/services/routing_service.py`
- Modify: `tests/test_routing_service.py`

**Step 1: Write failing test for cache hit**

Add to `tests/test_routing_service.py`:

```python
from unittest.mock import Mock, patch, AsyncMock


def test_route_and_complete_cache_hit(providers, tmp_path):
    """Test route_and_complete with cache hit."""
    db_path = str(tmp_path / "test.db")
    service = RoutingService(db_path=db_path, providers=providers)

    # Mock cache hit
    with patch.object(service.cost_tracker, 'check_cache') as mock_cache:
        mock_cache.return_value = {
            "cache_key": "test123",
            "response": "Cached response",
            "provider": "gemini",
            "model": "gemini-1.5-flash",
            "complexity": "simple",
            "tokens_in": 10,
            "tokens_out": 50,
            "cost": 0.001,
            "created_at": "2025-01-01",
            "hit_count": 1
        }

        import asyncio
        result = asyncio.run(service.route_and_complete(
            prompt="Test prompt",
            auto_route=False,
            max_tokens=1000
        ))

        assert result["response"] == "Cached response"
        assert result["cache_hit"] is True
        assert result["cost"] == 0.0  # Cache hits are free
        assert result["original_cost"] == 0.001
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_routing_service.py::test_route_and_complete_cache_hit -v`

Expected: FAIL with "object has no attribute 'route_and_complete'"

**Step 3: Implement route_and_complete with cache logic**

Add to `app/services/routing_service.py`:

```python
async def route_and_complete(
    self,
    prompt: str,
    auto_route: bool,
    max_tokens: int
) -> Dict[str, Any]:
    """Route prompt and execute completion with cache check.

    Args:
        prompt: User prompt to route
        auto_route: If True, use intelligent hybrid routing
        max_tokens: Maximum response tokens

    Returns:
        Dict with response, provider, model, cost, and metadata
    """
    # Check cache first
    cached = self.cost_tracker.check_cache(prompt, max_tokens)

    if cached:
        logger.info(f"Cache HIT: {cached['cache_key'][:16]}...")

        # Record cache hit
        self.cost_tracker.record_cache_hit(cached["cache_key"])

        # Log as request with $0 cost
        self.cost_tracker.log_request(
            prompt=prompt,
            complexity=cached["complexity"],
            provider="cache",
            model=cached["model"],
            tokens_in=0,
            tokens_out=0,
            cost=0.0
        )

        total_cost = self.cost_tracker.get_total_cost()

        return {
            "response": cached["response"],
            "provider": cached["provider"],
            "model": cached["model"],
            "strategy_used": "cached",
            "confidence": "high",
            "complexity_metadata": {
                "cached": True,
                "original_timestamp": cached["created_at"]
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

    # Get routing decision from engine
    context = RoutingContext(prompt=prompt)
    decision = self.engine.route(prompt=prompt, auto_route=auto_route, context=context)

    # Execute with selected provider
    provider = self.providers[decision.provider]
    response = await provider.send_message(prompt, max_tokens=max_tokens)

    # Extract response data
    response_text = response.get("response", response.get("text", ""))
    tokens_in = response.get("tokens_in", response.get("usage", {}).get("input_tokens", 0))
    tokens_out = response.get("tokens_out", response.get("usage", {}).get("output_tokens", 0))
    cost = response.get("cost", 0.0)

    # Store in cache
    self.cost_tracker.store_in_cache(
        prompt=prompt,
        max_tokens=max_tokens,
        response=response_text,
        provider=decision.provider,
        model=decision.model,
        complexity="unknown",  # Will be set by engine in future
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost=cost
    )

    # Log to database
    self.cost_tracker.log_request(
        prompt=prompt,
        complexity="unknown",
        provider=decision.provider,
        model=decision.model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost=cost
    )

    total_cost = self.cost_tracker.get_total_cost()
    cache_key = self.cost_tracker._generate_cache_key(prompt, max_tokens)

    return {
        "response": response_text,
        "provider": decision.provider,
        "model": decision.model,
        "strategy_used": decision.strategy_used,
        "confidence": decision.confidence,
        "complexity_metadata": decision.metadata,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost": cost,
        "total_cost_today": total_cost,
        "cache_hit": False,
        "original_cost": None,
        "savings": 0.0,
        "cache_key": cache_key,
        "routing_metadata": decision.metadata
    }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_routing_service.py::test_route_and_complete_cache_hit -v`

Expected: PASS

**Step 5: Commit**

```bash
git add app/services/routing_service.py tests/test_routing_service.py
git commit -m "feat: implement route_and_complete with cache integration"
```

---

## Task 3: Implement get_recommendation Method

**Files:**

- Modify: `app/services/routing_service.py`
- Modify: `tests/test_routing_service.py`

**Step 1: Write failing test**

Add to `tests/test_routing_service.py`:

```python
def test_get_recommendation(providers, tmp_path):
    """Test get_recommendation returns routing decision."""
    db_path = str(tmp_path / "test.db")
    service = RoutingService(db_path=db_path, providers=providers)

    result = service.get_recommendation(prompt="What is Python?")

    assert "provider" in result
    assert "model" in result
    assert "confidence" in result
    assert "strategy_used" in result
    assert result["strategy_used"] == "hybrid"  # Always uses hybrid
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_routing_service.py::test_get_recommendation -v`

Expected: FAIL with "object has no attribute 'get_recommendation'"

**Step 3: Implement get_recommendation**

Add to `app/services/routing_service.py`:

```python
def get_recommendation(self, prompt: str) -> Dict[str, Any]:
    """Preview routing decision without executing.

    Always uses auto_route=true (hybrid strategy) for recommendations.

    Args:
        prompt: Prompt to analyze

    Returns:
        Dict with routing decision and metadata
    """
    context = RoutingContext(prompt=prompt)
    decision = self.engine.route(prompt=prompt, auto_route=True, context=context)

    return {
        "provider": decision.provider,
        "model": decision.model,
        "confidence": decision.confidence,
        "strategy_used": decision.strategy_used,
        "reasoning": decision.reasoning,
        "metadata": decision.metadata
    }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_routing_service.py::test_get_recommendation -v`

Expected: PASS

**Step 5: Commit**

```bash
git add app/services/routing_service.py tests/test_routing_service.py
git commit -m "feat: implement get_recommendation for routing preview"
```

---

## Task 4: Implement get_routing_metrics Method

**Files:**

- Modify: `app/services/routing_service.py`
- Modify: `tests/test_routing_service.py`

**Step 1: Write failing test**

Add to `tests/test_routing_service.py`:

```python
def test_get_routing_metrics(providers, tmp_path):
    """Test get_routing_metrics returns analytics."""
    db_path = str(tmp_path / "test.db")
    service = RoutingService(db_path=db_path, providers=providers)

    result = service.get_routing_metrics(days=7)

    assert "cost_savings" in result
    assert "by_strategy" in result
    assert "by_confidence" in result
    assert isinstance(result["by_strategy"], list)
    assert isinstance(result["by_confidence"], list)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_routing_service.py::test_get_routing_metrics -v`

Expected: FAIL with "object has no attribute 'get_routing_metrics'"

**Step 3: Implement get_routing_metrics**

Add to `app/services/routing_service.py`:

```python
def get_routing_metrics(self, days: int = 7) -> Dict[str, Any]:
    """Get auto-route analytics from MetricsCollector.

    Args:
        days: Number of days of history to analyze

    Returns:
        Dict with cost savings, strategy distribution, confidence levels
    """
    metrics = self.engine.metrics

    return {
        "cost_savings": metrics.get_cost_savings(days=days),
        "by_strategy": metrics.aggregate_by_strategy(days=days),
        "by_confidence": metrics.aggregate_by_confidence(days=days)
    }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_routing_service.py::test_get_routing_metrics -v`

Expected: PASS

**Step 5: Commit**

```bash
git add app/services/routing_service.py tests/test_routing_service.py
git commit -m "feat: implement get_routing_metrics for analytics"
```

---

## Task 5: Update main.py Imports and Models

**Files:**

- Modify: `app/main.py:1-50`

**Step 1: Update imports section**

Replace lines 10-12 in `app/main.py`:

```python
# OLD (remove these lines)
from .complexity import score_complexity, get_complexity_metadata
from .providers import init_providers
from .router import Router, RoutingError
from .database import CostTracker

# NEW (replace with these)
from .providers import init_providers
from .database import CostTracker
from app.services.routing_service import RoutingService
```

**Step 2: Add auto_route field to CompleteRequest**

Modify `CompleteRequest` model around line 57:

```python
class CompleteRequest(BaseModel):
    """Request model for completion endpoint."""
    prompt: str = Field(..., min_length=1, description="User prompt")
    max_tokens: Optional[int] = Field(1000, ge=1, le=4000, description="Maximum response tokens")
    auto_route: bool = Field(False, description="Enable intelligent routing (hybrid strategy)")
    tokenizer_id: Optional[str] = Field(None, description="Optional HF repo id for tokenization metrics")
```

**Step 3: Add new fields to CompleteResponse**

Modify `CompleteResponse` model around line 64:

```python
class CompleteResponse(BaseModel):
    """Response model for completion endpoint."""
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
```

**Step 4: Update initialization section**

Replace lines 48-51:

```python
# OLD (remove these lines)
providers = init_providers()
router = Router(providers)
cost_tracker = CostTracker(db_path=os.getenv("DATABASE_PATH", "optimizer.db"))

# NEW (replace with these)
providers = init_providers()
routing_service = RoutingService(
    db_path=os.getenv("DATABASE_PATH", "optimizer.db"),
    providers=providers
)
```

**Step 5: Commit**

```bash
git add app/main.py
git commit -m "refactor: update imports and models for RoutingService integration"
```

---

## Task 6: Update /complete Endpoint

**Files:**

- Modify: `app/main.py:120-292`

**Step 1: Replace /complete endpoint implementation**

Replace the entire `complete_prompt` function (lines 120-292):

```python
@app.post("/complete", response_model=CompleteResponse)
async def complete_prompt(request: CompleteRequest):
    """
    Route and complete a prompt using optimal provider with caching.

    This is the main endpoint that:
    1. Checks response cache for instant results
    2. Routes using RoutingEngine (complexity or hybrid based on auto_route)
    3. Executes completion with selected provider
    4. Stores response in cache
    5. Tracks cost and routing metrics

    Args:
        request: CompleteRequest with prompt, max_tokens, and auto_route

    Returns:
        CompleteResponse with response text, metadata, and cost

    Raises:
        HTTPException: If routing or completion fails
    """
    try:
        result = await routing_service.route_and_complete(
            prompt=request.prompt,
            auto_route=request.auto_route,
            max_tokens=request.max_tokens
        )

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
        )

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
```

**Step 2: Test endpoint manually**

Run server:

```bash
python app/main.py
```

Test with curl:

```bash
curl -X POST http://localhost:8000/complete \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is Python?", "auto_route": false}'
```

Expected: 200 response with strategy_used="complexity"

**Step 3: Commit**

```bash
git add app/main.py
git commit -m "refactor: update /complete endpoint to use RoutingService"
```

---

## Task 7: Update /recommendation Endpoint

**Files:**

- Modify: `app/main.py:342-368`

**Step 1: Replace /recommendation endpoint**

Replace the `get_recommendation` function (lines 342-368):

```python
@app.get("/recommendation")
async def get_recommendation(prompt: str):
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
```

**Step 2: Test endpoint**

```bash
curl "http://localhost:8000/recommendation?prompt=What%20is%20Python?"
```

Expected: 200 response with strategy_used="hybrid"

**Step 3: Commit**

```bash
git add app/main.py
git commit -m "refactor: update /recommendation to use hybrid routing"
```

---

## Task 8: Add /routing/metrics Endpoint

**Files:**

- Modify: `app/main.py` (add after /recommendation)

**Step 1: Add new endpoint after /recommendation**

Add this new endpoint after the `/recommendation` function:

```python
@app.get("/routing/metrics")
async def get_routing_metrics(days: int = 7):
    """
    Get auto-routing analytics for monitoring and ROI tracking.

    Returns cost savings, strategy distribution, and confidence levels
    over the specified time period.

    Args:
        days: Number of days of history to analyze (default: 7)

    Returns:
        Dict with cost_savings, by_strategy, and by_confidence aggregations
    """
    try:
        return routing_service.get_routing_metrics(days=days)

    except Exception as e:
        logger.error(f"Error fetching routing metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
```

**Step 2: Test endpoint**

```bash
curl "http://localhost:8000/routing/metrics?days=30"
```

Expected: 200 response with cost_savings, by_strategy, by_confidence

**Step 3: Commit**

```bash
git add app/main.py
git commit -m "feat: add /routing/metrics endpoint for analytics"
```

---

## Task 9: Add /routing/decision Endpoint

**Files:**

- Modify: `app/main.py` (add after /routing/metrics)

**Step 1: Add new endpoint after /routing/metrics**

```python
@app.get("/routing/decision")
async def get_routing_decision(prompt: str, auto_route: bool = True):
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
```

**Step 2: Test endpoint**

```bash
curl "http://localhost:8000/routing/decision?prompt=Debug%20this%20Python%20code"
```

Expected: 200 response with decision and metadata

**Step 3: Commit**

```bash
git add app/main.py
git commit -m "feat: add /routing/decision endpoint for debug transparency"
```

---

## Task 10: Remove Legacy Files

**Files:**

- Delete: `app/router.py`
- Delete: `app/complexity.py`

**Step 1: Verify no imports remain**

Search for remaining references:

```bash
grep -r "from.*router import" app/ tests/ || echo "No imports found"
grep -r "from.*complexity import" app/ tests/ || echo "No imports found"
```

Expected: "No imports found" for both

**Step 2: Remove legacy files**

```bash
git rm app/router.py app/complexity.py
```

**Step 3: Commit**

```bash
git commit -m "refactor: remove legacy Router and complexity modules"
```

---

## Task 11: Run Full Test Suite

**Files:**

- All test files

**Step 1: Run complete test suite**

```bash
pytest -v --tb=short
```

Expected: 39+ tests passing (new RoutingService tests added)

**Step 2: Check for any failures**

If failures occur:

- Read error messages carefully
- Fix issues one at a time
- Re-run tests after each fix

**Step 3: Verify new endpoints work**

Manual testing checklist:

```bash
# 1. POST /complete with auto_route=false
curl -X POST http://localhost:8000/complete \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello", "auto_route": false}'

# 2. POST /complete with auto_route=true
curl -X POST http://localhost:8000/complete \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Debug this code", "auto_route": true}'

# 3. GET /recommendation
curl "http://localhost:8000/recommendation?prompt=Hello"

# 4. GET /routing/metrics
curl "http://localhost:8000/routing/metrics?days=7"

# 5. GET /routing/decision
curl "http://localhost:8000/routing/decision?prompt=Hello"
```

**Step 4: Commit any test fixes**

```bash
git add tests/
git commit -m "test: fix integration tests for RoutingService"
```

---

## Task 12: Update Health Check Endpoint

**Files:**

- Modify: `app/main.py:110-118`

**Step 1: Enhance health check with routing info**

Modify the `/health` endpoint:

```python
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "providers_available": list(routing_service.providers.keys()),
        "routing_engine": "v2",  # NEW: Indicate Phase 2 routing
        "auto_route_enabled": routing_service.engine.track_metrics,
        "version": "2.0.0"  # Bump version for Phase 2
    }
```

**Step 2: Test health check**

```bash
curl http://localhost:8000/health
```

Expected: 200 with routing_engine="v2"

**Step 3: Commit**

```bash
git add app/main.py
git commit -m "feat: update health check for Phase 2 routing engine"
```

---

## Task 13: Final Integration Verification

**Files:**

- All files

**Step 1: Run full test suite one more time**

```bash
pytest -v
```

Expected: All tests passing

**Step 2: Start server and verify all endpoints**

```bash
python app/main.py
```

Visit http://localhost:8000/docs and test each endpoint through Swagger UI:

- ✅ POST /complete (with auto_route=false)
- ✅ POST /complete (with auto_route=true)
- ✅ GET /recommendation
- ✅ GET /routing/metrics
- ✅ GET /routing/decision
- ✅ GET /health
- ✅ GET /stats
- ✅ GET /providers

**Step 3: Check git status**

```bash
git status
```

Expected: Clean working directory, all changes committed

**Step 4: Review commit history**

```bash
git log --oneline -15
```

Expected: ~13 commits showing incremental progress

**Step 5: Final commit if needed**

If any uncommitted changes:

```bash
git add .
git commit -m "chore: final cleanup for FastAPI integration"
```

---

## Task 14: Push and Create Pull Request

**Files:**

- None (Git operations only)

**Step 1: Push branch to remote**

```bash
git push -u origin feature/fastapi-integration
```

Expected: Branch pushed successfully

**Step 2: Verify branch is up**

```bash
git branch -vv
```

Expected: Shows tracking relationship with origin

**Step 3: Ready for merge**

At this point:

- All tests passing (39+ tests)
- All endpoints working
- Clean commit history
- Ready to merge into `feature/phase2-auto-routing`

---

## Success Criteria

### Functional Requirements

- ✅ POST /complete supports `auto_route` parameter
- ✅ auto_route=false uses complexity routing (backward compatible)
- ✅ auto_route=true uses hybrid routing (intelligent)
- ✅ Response cache integrated and working
- ✅ Cost tracking preserved for all requests
- ✅ Metrics automatically tracked to routing_metrics table
- ✅ New analytics endpoints return accurate data

### Code Quality

- ✅ All existing tests pass
- ✅ New unit tests for RoutingService (4+ tests)
- ✅ Clean separation: FastAPI → Service → Core
- ✅ No legacy code remaining (router.py, complexity.py removed)
- ✅ Proper error handling with HTTPException

### Integration

- ✅ /health endpoint shows routing_engine="v2"
- ✅ All endpoints accessible via Swagger UI
- ✅ Manual testing checklist complete
- ✅ Ready for production deployment

---

## Troubleshooting

### Import Errors

**Problem:** `ModuleNotFoundError: No module named 'app.services'`

**Solution:**

```bash
# Ensure __init__.py exists
touch app/services/__init__.py
```

### Test Failures

**Problem:** Tests fail with "fixture not found"

**Solution:**

```bash
# Ensure pytest is using correct Python
python3 -m pytest -v
```

### Provider Execution Errors

**Problem:** `AttributeError: 'dict' object has no attribute 'send_message'`

**Solution:** Provider clients need to be actual provider objects, not dictionaries. Check `init_providers()` returns correct format.

### Database Errors

**Problem:** `sqlite3.OperationalError: no such table: routing_metrics`

**Solution:**

```bash
# Run database migrations
python -c "from app.database import create_routing_metrics_table; create_routing_metrics_table()"
```

---

## References

### Design Documents

- Phase 2 Design: `docs/plans/2025-01-11-phase2-auto-routing-design.md`
- FastAPI Integration Design: `docs/plans/2025-01-11-fastapi-integration-design.md`

### Key Files

- `app/routing/engine.py` - RoutingEngine (Phase 2)
- `app/routing/strategy.py` - ComplexityStrategy, LearningStrategy, HybridStrategy
- `app/routing/metrics.py` - MetricsCollector
- `app/database.py` - CostTracker, database operations
- `app/providers.py` - Provider clients (unchanged)

### Testing Commands

```bash
# Run all tests
pytest -v

# Run specific test file
pytest tests/test_routing_service.py -v

# Run with coverage
pytest --cov=app --cov-report=html

# Start development server
python app/main.py
```
