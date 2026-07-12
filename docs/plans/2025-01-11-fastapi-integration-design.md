# FastAPI Integration Design - Phase 2 Auto-Routing

**Date:** 2025-01-11
**Status:** Design Complete - Ready for Implementation
**Author:** AI Cost Optimizer Team

## Executive Summary

This design integrates Phase 2 Auto-Routing (RoutingEngine + MetricsCollector) into the FastAPI application. We replace the legacy Router class with a clean three-layer architecture: FastAPI endpoints, RoutingService business logic, and RoutingEngine core. This enables intelligent model selection via the `auto_route` parameter while maintaining backward compatibility.

**Key Benefits:**

- Intelligent routing with learning-based optimization
- Comprehensive metrics tracking for ROI analysis
- Clean separation of concerns (HTTP, business logic, routing)
- Zero downtime migration (auto_route defaults to false)

**Implementation Effort:** ~3 hours

---

## Architecture Overview

### Three-Layer Design

```
┌─────────────────────────────────────────────┐
│           FastAPI Layer                     │
│  (HTTP, request/response models)            │
│  - /complete, /recommendation, /stats       │
│  - New: /routing/metrics, /routing/decision │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│        Service Layer (NEW)                  │
│  app/services/routing_service.py            │
│  - Cache checking                           │
│  - Provider execution                       │
│  - Cost tracking coordination               │
│  - Response formatting                      │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│          Core Layer (Phase 2)               │
│  app/routing/                               │
│  - RoutingEngine (facade)                   │
│  - Strategy Pattern (3 strategies)          │
│  - MetricsCollector (analytics)             │
└─────────────────────────────────────────────┘
```

### Data Flow

```
1. Client sends request → FastAPI endpoint
2. FastAPI validates → calls RoutingService
3. RoutingService checks cache → CostTracker
4. Cache miss → RoutingService calls RoutingEngine
5. RoutingEngine selects strategy → routes prompt
6. RoutingService executes → provider API
7. RoutingService tracks metrics → MetricsCollector
8. RoutingService logs cost → CostTracker
9. Response returns → Client
```

**Cache Hit Path:** Steps 1-3, then return cached response (skip steps 4-8).

---

## Component Design

### 1. RoutingService (NEW)

**File:** `app/services/routing_service.py`

**Purpose:** Bridge between FastAPI and RoutingEngine. Handles FastAPI-specific concerns without polluting core routing logic.

**Class Definition:**

```python
class RoutingService:
    """FastAPI service layer for intelligent routing."""

    def __init__(self, db_path: str, providers: dict):
        self.engine = RoutingEngine(db_path, track_metrics=True)
        self.providers = providers
        self.cost_tracker = CostTracker(db_path)

    async def route_and_complete(
        self,
        prompt: str,
        auto_route: bool,
        max_tokens: int
    ) -> dict:
        """Route prompt and execute completion.

        Flow:
        1. Check cache (via cost_tracker)
        2. If miss: Get routing decision from engine
        3. Execute with selected provider
        4. Store in cache
        5. Return formatted response
        """

    def get_recommendation(self, prompt: str) -> dict:
        """Preview routing decision without executing.

        Uses auto_route=true (hybrid strategy) by default.
        Returns RoutingDecision with metadata.
        """

    def get_routing_metrics(self, days: int = 7) -> dict:
        """Get auto-route analytics from MetricsCollector.

        Returns cost savings, strategy distribution, confidence levels.
        """
```

**Key Responsibilities:**

- **Cache Integration** - Reuse existing CostTracker cache logic
- **Provider Execution** - Get decision from engine, call provider API
- **Cost Tracking** - Log requests to database (preserve existing behavior)
- **Metrics Coordination** - RoutingEngine tracks metrics automatically
- **Response Formatting** - Convert RoutingDecision to FastAPI models

**Error Handling:**

- Catch all exceptions from RoutingEngine
- Convert to HTTPException with appropriate status codes
- RoutingEngine already has fallback to complexity (internal safety)

---

### 2. FastAPI Endpoint Changes

#### Modified: POST /complete

**Request Model:**

```python
class CompleteRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    max_tokens: Optional[int] = Field(1000, ge=1, le=4000)
    auto_route: bool = Field(False)  # NEW: Enable intelligent routing
    tokenizer_id: Optional[str] = None
```

**Response Model Changes:**

```python
class CompleteResponse(BaseModel):
    # Existing fields preserved
    response: str
    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    cost: float
    total_cost_today: float
    cache_hit: bool

    # NEW fields
    strategy_used: str  # "complexity", "learning", "hybrid", "hybrid_fallback"
    confidence: str     # "high", "medium", "low"
    routing_metadata: dict  # Full RoutingDecision.metadata
```

**Implementation:**

```python
@app.post("/complete", response_model=CompleteResponse)
async def complete_prompt(request: CompleteRequest):
    result = await routing_service.route_and_complete(
        prompt=request.prompt,
        auto_route=request.auto_route,
        max_tokens=request.max_tokens
    )
    return CompleteResponse(**result)
```

#### Modified: GET /recommendation

**Changes:**

- Always uses `auto_route=true` (hybrid strategy)
- Returns RoutingDecision with full metadata
- No longer uses legacy complexity scoring

**Response:**

```json
{
  "provider": "openrouter",
  "model": "openrouter/deepseek/deepseek-coder",
  "confidence": "high",
  "strategy_used": "hybrid",
  "reasoning": "Code pattern detected (validated by complexity)",
  "metadata": {
    "pattern": "code",
    "complexity": 0.82,
    "quality_score": 0.95,
    "cost_estimate": 0.00014,
    "validation": "validated"
  }
}
```

#### New: GET /routing/metrics

**Purpose:** Auto-routing analytics for monitoring and ROI tracking.

**Query Parameters:**

- `days` (optional, default=7): Days of history to analyze

**Response:**

```json
{
  "cost_savings": {
    "total_saved": 0.045,
    "percent_saved": 23.5,
    "intelligent_cost": 0.147,
    "baseline_cost": 0.192,
    "period_days": 7
  },
  "by_strategy": [
    {
      "strategy": "hybrid",
      "count": 142,
      "avg_cost": 0.00089,
      "high_confidence_pct": 78.2
    },
    {
      "strategy": "complexity",
      "count": 58,
      "avg_cost": 0.0012,
      "high_confidence_pct": 0
    }
  ],
  "by_confidence": [
    { "confidence": "high", "count": 111, "avg_cost": 0.00082 },
    { "confidence": "medium", "count": 89, "avg_cost": 0.00095 }
  ]
}
```

**Implementation:**

```python
@app.get("/routing/metrics")
async def get_routing_metrics(days: int = 7):
    return routing_service.get_routing_metrics(days=days)
```

#### New: GET /routing/decision

**Purpose:** Detailed routing explanation for debugging and transparency.

**Query Parameters:**

- `prompt` (required): Prompt to analyze
- `auto_route` (optional, default=true): Use intelligent routing

**Response:**

```json
{
  "decision": {
    "provider": "claude",
    "model": "claude-3-5-sonnet-20241022",
    "confidence": "high",
    "strategy_used": "hybrid",
    "reasoning": "Complex analysis prompt (validated by complexity)",
    "fallback_used": false
  },
  "metadata": {
    "pattern": "analysis",
    "complexity": 0.78,
    "quality_score": 0.92,
    "cost_estimate": 0.003,
    "validation": "validated",
    "complexity_score": 0.78
  }
}
```

---

## Migration Strategy

### File Operations

**Remove (Legacy):**

```bash
rm app/router.py          # Old Router class
rm app/complexity.py      # Replaced by app/routing/complexity.py
```

**Keep (Existing):**

```bash
app/database.py           # CostTracker, response_cache
app/providers.py          # Provider clients (unchanged)
app/learning.py           # QueryPatternAnalyzer (Phase 1)
```

**Add (Phase 2):**

```bash
app/routing/models.py     # RoutingDecision, RoutingContext
app/routing/strategy.py   # ComplexityStrategy, LearningStrategy, HybridStrategy
app/routing/complexity.py # score_complexity() function
app/routing/engine.py     # RoutingEngine facade
app/routing/metrics.py    # MetricsCollector
```

**Create (Integration):**

```bash
app/services/routing_service.py  # NEW service layer
```

**Modify:**

```bash
app/main.py               # Update imports, initialize RoutingService
```

### Database Schema

**No changes required!**

- `routing_metrics` table exists (created by Phase 2)
- `response_cache` table exists (Phase 1)
- All indexes already in place

### Code Changes in main.py

**Imports:**

```python
# Remove
from .router import Router, RoutingError
from .complexity import score_complexity, get_complexity_metadata

# Add
from app.services.routing_service import RoutingService
from app.routing.models import RoutingDecision
```

**Initialization:**

```python
# OLD
providers = init_providers()
router = Router(providers)
cost_tracker = CostTracker(db_path="optimizer.db")

# NEW
providers = init_providers()
routing_service = RoutingService(
    db_path=os.getenv("DATABASE_PATH", "optimizer.db"),
    providers=providers
)
```

**Endpoint Updates:**

```python
# /complete endpoint
@app.post("/complete", response_model=CompleteResponse)
async def complete_prompt(request: CompleteRequest):
    result = await routing_service.route_and_complete(
        prompt=request.prompt,
        auto_route=request.auto_route,
        max_tokens=request.max_tokens
    )
    return CompleteResponse(**result)

# /recommendation endpoint
@app.get("/recommendation")
async def get_recommendation(prompt: str):
    return routing_service.get_recommendation(prompt=prompt)
```

---

## Backward Compatibility

### Default Behavior Unchanged

**Key Decision:** `auto_route: bool = False` by default.

**Result:** Existing behavior preserved:

- No clients exist (user is sole client)
- Default uses complexity-based routing (safe, predictable)
- Clients opt into intelligent routing explicitly

### API Compatibility

**POST /complete:**

- All existing fields remain
- `auto_route` is optional (defaults to false)
- Response adds new fields but preserves all existing fields

**GET /recommendation:**

- Query parameter unchanged (still accepts `?prompt=...`)
- Response structure enhanced but backward compatible

**All other endpoints:**

- No changes to `/health`, `/stats`, `/providers`, `/cache/stats`, `/feedback`, `/quality/stats`, `/insights`

### Migration Risk: LOW

**Why low risk:**

1. No breaking changes to existing APIs
2. Default behavior matches legacy system
3. New features are opt-in
4. Comprehensive error handling and fallbacks
5. Single client (easy to update if needed)

---

## Error Handling Strategy

### Three Layers of Safety

**1. RoutingEngine Internal Fallback**

```python
# RoutingEngine already handles:
- Invalid decisions → fallback to complexity
- Database errors → fallback to complexity
- Strategy failures → fallback to complexity
```

**2. RoutingService Exception Handling**

```python
# RoutingService wraps all operations:
try:
    decision = self.engine.route(prompt, auto_route)
    result = await self._execute_with_provider(decision)
    return result
except Exception as e:
    logger.error(f"Routing failed: {e}")
    raise HTTPException(status_code=503, detail="Routing unavailable")
```

**3. FastAPI Error Responses**

```python
# Preserve existing error format:
{
  "detail": "Routing unavailable",
  "status_code": 503
}
```

### Error Scenarios

| Scenario             | RoutingEngine Behavior  | RoutingService Behavior | Client Impact               |
| -------------------- | ----------------------- | ----------------------- | --------------------------- |
| Database locked      | Fallback to complexity  | Log warning, continue   | None (gets response)        |
| Learning unavailable | Use complexity strategy | Continue normally       | None (transparent fallback) |
| Invalid provider     | Use fallback chain      | Continue normally       | None (automatic retry)      |
| All providers down   | Raise exception         | HTTPException 503       | Error response              |
| Invalid prompt       | N/A                     | HTTPException 400       | Error response              |

---

## Testing Strategy

### Unit Tests (RoutingService)

**File:** `tests/test_routing_service.py`

**Coverage:**

1. `test_route_and_complete_cache_hit` - Verify cache integration
2. `test_route_and_complete_cache_miss` - Full routing flow
3. `test_route_and_complete_with_auto_route_false` - Complexity routing
4. `test_route_and_complete_with_auto_route_true` - Hybrid routing
5. `test_get_recommendation` - Preview logic
6. `test_get_routing_metrics` - Metrics aggregation
7. `test_error_handling` - Exception conversion

### Integration Tests (FastAPI)

**File:** `tests/test_main_integration.py`

**Coverage:**

1. `test_complete_endpoint_default_behavior` - Backward compatibility
2. `test_complete_endpoint_with_auto_route` - New feature
3. `test_recommendation_endpoint` - Hybrid recommendations
4. `test_routing_metrics_endpoint` - Analytics API
5. `test_routing_decision_endpoint` - Debug API

### Manual Testing Checklist

```
[ ] POST /complete with auto_route=false → uses complexity routing
[ ] POST /complete with auto_route=true → uses hybrid routing
[ ] Cache hit returns instant response with $0 cost
[ ] Cache miss executes routing and caches result
[ ] GET /recommendation returns hybrid recommendations
[ ] GET /routing/metrics shows cost savings
[ ] GET /routing/decision explains routing logic
[ ] All existing endpoints unchanged (/stats, /providers, etc.)
[ ] Error cases return appropriate HTTP status codes
```

---

## Implementation Plan Overview

### Phase 1: Core Service (1 hour)

1. Create `app/services/routing_service.py`
2. Implement `route_and_complete()` with cache integration
3. Implement `get_recommendation()`
4. Implement `get_routing_metrics()`
5. Unit tests for RoutingService

### Phase 2: FastAPI Integration (1 hour)

1. Update `app/main.py` imports and initialization
2. Modify `/complete` endpoint to use RoutingService
3. Modify `/recommendation` endpoint
4. Add `/routing/metrics` endpoint
5. Add `/routing/decision` endpoint
6. Update request/response models

### Phase 3: Cleanup & Testing (1 hour)

1. Remove `app/router.py` and `app/complexity.py`
2. Run full test suite
3. Manual testing of all endpoints
4. Update API documentation
5. Commit and push

**Total Estimated Time:** 3 hours

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

### Non-Functional Requirements

- ✅ Zero breaking changes to existing API
- ✅ All existing tests pass
- ✅ New unit tests for RoutingService (7+ tests)
- ✅ Integration tests for new endpoints (5+ tests)
- ✅ Error handling provides clear messages
- ✅ Logging at appropriate levels

### Business Requirements

- ✅ Can measure ROI via /routing/metrics
- ✅ Can debug routing decisions via /routing/decision
- ✅ Can preview recommendations via /recommendation
- ✅ Gradual rollout possible (auto_route=false default)

---

## Future Enhancements

### Phase 3: Advanced Features (Not in Scope)

1. **Per-User Routing Preferences** - Store user preferences for auto_route
2. **A/B Testing Framework** - Automatically split traffic for testing
3. **Cost Budget Limits** - Reject requests exceeding budget
4. **Real-Time Metrics Dashboard** - WebSocket streaming of routing decisions
5. **Custom Routing Rules** - Allow users to define routing preferences

### Phase 4: Production Optimizations (Not in Scope)

1. **Connection Pooling** - Reuse database connections
2. **Caching Layer** - Redis for hot path optimization
3. **Async Metrics** - Background task for metrics writing
4. **Rate Limiting** - Per-user or per-endpoint limits

---

## Appendix A: Key Design Decisions

### Why Service Layer?

**Decision:** Add `app/services/routing_service.py` instead of putting logic in `main.py`.

**Rationale:**

- Separation of concerns (HTTP vs business logic)
- RoutingEngine stays pure (no FastAPI dependencies)
- Easy to test business logic in isolation
- Natural place for cross-cutting concerns

**Alternative Considered:** Direct integration in main.py (rejected - mixes concerns)

### Why auto_route=false Default?

**Decision:** Default to complexity-based routing, not intelligent routing.

**Rationale:**

- Safe, predictable behavior
- Users opt into learning-based routing explicitly
- Allows gradual rollout and A/B testing
- Preserves existing behavior (backward compatible)

**Alternative Considered:** auto_route=true default (rejected - too aggressive for initial rollout)

### Why /recommendation Uses Hybrid?

**Decision:** GET /recommendation always uses `auto_route=true`.

**Rationale:**

- Recommendations should show "best" routing, not baseline
- Users expect intelligent suggestions
- Complexity-based routing is boring for previews

**Alternative Considered:** Add query param (rejected - over-engineering for preview endpoint)

### Why Remove Old Router?

**Decision:** Complete replacement, not gradual migration.

**Rationale:**

- Single client (no backward compatibility needs)
- Reduces code complexity and confusion
- Forces commitment to new architecture
- Easier to maintain single routing system

**Alternative Considered:** Keep both with flag (rejected - unnecessary complexity)

---

## Appendix B: API Response Examples

### POST /complete (auto_route=false)

**Request:**

```json
{
  "prompt": "What is Python?",
  "max_tokens": 1000,
  "auto_route": false
}
```

**Response:**

```json
{
  "response": "Python is a high-level programming language...",
  "provider": "gemini",
  "model": "gemini-1.5-flash",
  "strategy_used": "complexity",
  "confidence": "medium",
  "complexity_metadata": { "complexity": 0.2, "token_count": 15 },
  "tokens_in": 15,
  "tokens_out": 87,
  "cost": 0.000012,
  "total_cost_today": 0.234,
  "cache_hit": false,
  "routing_metadata": {
    "pattern": "unknown",
    "complexity": 0.2
  }
}
```

### POST /complete (auto_route=true)

**Request:**

```json
{
  "prompt": "Debug this Python function that's throwing a TypeError",
  "max_tokens": 2000,
  "auto_route": true
}
```

**Response:**

```json
{
  "response": "The TypeError is likely caused by...",
  "provider": "openrouter",
  "model": "openrouter/deepseek/deepseek-coder",
  "strategy_used": "hybrid",
  "confidence": "high",
  "complexity_metadata": { "complexity": 0.75, "token_count": 45 },
  "tokens_in": 45,
  "tokens_out": 312,
  "cost": 0.000043,
  "total_cost_today": 0.234,
  "cache_hit": false,
  "routing_metadata": {
    "pattern": "code",
    "complexity": 0.75,
    "quality_score": 0.95,
    "cost_estimate": 0.000014,
    "validation": "validated"
  }
}
```

### GET /routing/metrics?days=30

**Response:**

```json
{
  "cost_savings": {
    "total_saved": 0.187,
    "percent_saved": 31.2,
    "intelligent_cost": 0.412,
    "baseline_cost": 0.599,
    "period_days": 30
  },
  "by_strategy": [
    {
      "strategy": "hybrid",
      "count": 523,
      "avg_cost": 0.000788,
      "high_confidence_pct": 82.4
    },
    {
      "strategy": "complexity",
      "count": 189,
      "avg_cost": 0.001203,
      "high_confidence_pct": 0
    }
  ],
  "by_confidence": [
    { "confidence": "high", "count": 431, "avg_cost": 0.000712 },
    { "confidence": "medium", "count": 281, "avg_cost": 0.000891 }
  ]
}
```

---

## Document History

| Date       | Version | Changes                 |
| ---------- | ------- | ----------------------- |
| 2025-01-11 | 1.0     | Initial design complete |
