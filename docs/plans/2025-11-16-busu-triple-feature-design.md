# BUSU Triple Feature: Production + Intelligence + Performance

**Date**: November 16, 2025
**Status**: Design Approved
**Goal**: Deliver production-hardened, intelligent, high-performance system in one 10-12 hour session

---

## Context

**Current State**: Production Feedback Loop complete (Tasks 1-8), 62/68 tests passing, 6 PostgreSQL connection failures

**Target State**: 90+ tests passing, Redis caching operational, A/B testing framework live, measurable performance gains

**Approach**: Feature-Complete Verticals—build three integrated features spanning production, intelligence, and performance

---

## Success Criteria

### Must-Haves

- All tests pass (target: 92/92)
- Redis caching works with <10ms response time
- A/B testing framework operational
- Visible performance improvements with before/after metrics

### Nice-to-Haves

- Advanced ML pattern recognition
- Full authentication system
- Comprehensive benchmarking suite

---

## Feature Selection

### Feature 1: Real-Time Metrics Dashboard with Redis Caching (3-4 hours)

**Production**: Fix 6 failing tests, deploy PostgreSQL + Redis via Docker Compose, full stack running locally
**Intelligence**: Live metrics showing routing decisions, confidence levels, cost savings in real-time
**Performance**: Redis caching for sub-10ms metric queries, instant dashboard updates

### Feature 2: A/B Testing Framework with Auto-Reporting (4-5 hours)

**Production**: Robust experiment tracking with PostgreSQL, statistically significant result detection
**Intelligence**: Scientific strategy comparison (Complexity vs Learning vs Hybrid), automatic winner detection
**Performance**: Efficient experiment allocation with minimal overhead, concurrent experiment support

### Feature 3: Async Optimization & Connection Pooling (2-3 hours)

**Production**: Full async/await throughout codebase, proper connection lifecycle management
**Intelligence**: Request batching for similar prompts, smart queue management
**Performance**: 5-10x throughput improvement, <50ms latency for cached requests

**Priority**: Feature 1 → Feature 2 → Feature 3 (time permitting)

---

## System Architecture

### Enhanced Stack

```
FastAPI Layer (Enhanced)
├─ NEW: /experiments/start, /experiments/results, /metrics/live
└─ EXISTING: /complete, /recommendation, /routing/metrics

Service Layer (Optimized)
├─ NEW: Redis cache check (10ms) before DB cache (50ms)
├─ NEW: Experiment allocation & tracking
└─ ENHANCED: Full async/await, connection pooling

Core Routing (Unchanged)
├─ RoutingEngine
├─ 3 Strategies
└─ MetricsCollector

Storage Layer (Enhanced)
├─ PostgreSQL (async)
├─ Redis (caching)
└─ Connection pools
```

### New Components

**1. RedisCache** (`app/cache/redis_cache.py`)

- Sub-10ms response caching
- Metrics caching for dashboard
- Automatic TTL management
- Fallback to PostgreSQL if Redis unavailable

**2. ExperimentTracker** (`app/experiments/tracker.py`)

- A/B test allocation (user_id → strategy assignment)
- Statistical significance calculation (chi-square tests)
- Automatic winner detection
- Performance metrics per strategy

**3. AsyncConnectionPool** (`app/database/pool.py`)

- PostgreSQL async connection pooling
- Redis connection pooling
- Health checks and auto-reconnect
- Resource limits and monitoring

**4. MetricsDashboard** (`app/api/dashboard.py`)

- Real-time WebSocket endpoint for live metrics
- Historical trend queries with Redis caching
- Cost savings visualization data
- Experiment results summary

### Docker Compose Stack

```yaml
services:
  postgres:
    image: postgres:15
    volumes: [./data/postgres:/var/lib/postgresql/data]

  redis:
    image: redis:7-alpine
    volumes: [./data/redis:/data]

  api:
    build: .
    depends_on: [postgres, redis]
    environment:
      DATABASE_URL: postgresql+asyncpg://...
      REDIS_URL: redis://redis:6379
```

---

## Data Flow

### Feature 1: Real-Time Metrics with Redis

```
Request → Check Redis cache (key: "metrics:latest")
         ├─ HIT (10ms) → Return cached metrics
         └─ MISS → Query PostgreSQL (50ms)
                 → Aggregate metrics
                 → Store in Redis (TTL: 30s)
                 → Return fresh metrics

WebSocket /metrics/live:
  - Push updates every 5 seconds
  - Batch all metric queries through Redis
  - Minimal PostgreSQL load
```

### Feature 2: A/B Testing

```
POST /experiments/start:
  1. Create experiment record (PostgreSQL)
  2. Define: control_strategy, test_strategy, sample_size
  3. Store experiment config in Redis for fast lookup

POST /complete with experiment_id:
  1. Hash user_id → determine assignment (control vs test)
  2. Route using assigned strategy
  3. Track: strategy, latency, cost, quality
  4. Store in experiment_results table
  5. Background: Check if sample_size reached
     - If yes: Run chi-square test for significance
     - If significant: Mark winner, notify

GET /experiments/{id}/results:
  1. Check Redis cache first
  2. Aggregate: avg_cost, avg_latency, quality_score per strategy
  3. Calculate: p-value, confidence_interval, winner
  4. Return with visual data for charts
```

### Feature 3: Async Optimization

```
Before:
  await db.execute(query)  # Synchronous, blocking

After:
  async with db_pool.acquire() as conn:
    await conn.execute(query)  # Non-blocking, pooled

Performance Gains:
  - Concurrent requests: 50 → 500 req/sec
  - P95 latency: 200ms → 50ms
  - Connection overhead: 50ms → 2ms (pooled)
```

### Cache Hierarchy

```
Level 1: Redis (10ms, hot data, TTL 30-300s)
  - Latest metrics
  - Active experiments
  - Frequent prompts

Level 2: PostgreSQL cache table (50ms, warm data)
  - response_cache table
  - Historical metrics

Level 3: Provider API (500-3000ms, cold)
  - Fresh LLM responses
```

---

## Error Handling

### 1. Graceful Degradation (Redis failures)

```python
async def get_metrics():
    try:
        cached = await redis.get("metrics:latest")
        if cached:
            return cached
    except RedisError as e:
        logger.warning(f"Redis unavailable: {e}, falling back to PostgreSQL")

    return await postgres.query_metrics()
```

### 2. Circuit Breaker (PostgreSQL overload)

```python
if postgres_failure_count > 5:
    circuit_open = True
    return cached_response  # Serve stale data rather than fail

# Auto-reset after 60 seconds
```

### 3. Experiment Safety

```python
# Never fail a request due to experiment tracking
try:
    await experiment_tracker.record(result)
except Exception as e:
    logger.error(f"Experiment tracking failed: {e}")
    # Continue - user gets response regardless
```

---

## Testing Strategy

### Current State

- 68 tests total
- 62 passing, 6 failing (PostgreSQL connection issues)

### Feature 1 Tests (8 new)

- `test_redis_cache_hit_performance()` - Verify <10ms
- `test_redis_fallback_to_postgres()` - Graceful degradation
- `test_metrics_dashboard_websocket()` - Real-time updates
- `test_docker_compose_stack_healthy()` - Integration test
- 4 more covering edge cases

### Feature 2 Tests (10 new)

- `test_experiment_creation()` - Setup experiment
- `test_user_assignment_deterministic()` - Same user → same strategy
- `test_statistical_significance()` - Chi-square calculations
- `test_experiment_results_caching()` - Redis performance
- 6 more covering allocation, winner detection, edge cases

### Feature 3 Tests (6 new)

- `test_async_connection_pooling()` - Pool behavior
- `test_concurrent_requests_performance()` - Load test
- `test_connection_lifecycle()` - Cleanup
- 3 more covering error handling

**Total: 68 + 24 = 92 tests, targeting 100% pass rate**

### Test Execution Strategy

1. Fix 6 failing tests FIRST (get PostgreSQL running)
2. Write tests BEFORE implementation (TDD)
3. Run full suite after each feature
4. Integration test at end with real Docker Compose stack

---

## Implementation Timeline

### Hours 1-4: Feature 1 - Real-Time Metrics Dashboard with Redis

- **Hour 1**: Fix 6 failing tests, get PostgreSQL + Redis running via Docker Compose
- **Hour 2**: Implement RedisCache class, connection pooling, integration tests
- **Hour 3**: Build /metrics/live WebSocket endpoint, real-time updates
- **Hour 4**: Dashboard endpoint with Redis caching, verify <10ms response times

### Hours 5-8: Feature 2 - A/B Testing Framework

- **Hour 5**: ExperimentTracker class, PostgreSQL schema, deterministic user assignment
- **Hour 6**: POST /experiments/start, GET /experiments/results endpoints
- **Hour 7**: Statistical significance calculation, winner detection logic
- **Hour 8**: Integration with routing service, end-to-end experiment flow testing

### Hours 9-12: Feature 3 - Async Optimization (if time permits)

- **Hour 9**: AsyncConnectionPool, migrate database calls to async
- **Hour 10**: Full async/await throughout service layer
- **Hour 11**: Load testing, performance benchmarking
- **Hour 12**: Documentation updates, final integration testing

---

## Success Metrics

### Production Hardening

- ✅ 90+ tests passing (target: 92/92)
- ✅ Full Docker Compose stack running (PostgreSQL + Redis + API)
- ✅ Zero errors in logs during smoke test

### Intelligence

- ✅ A/B testing framework operational
- ✅ Real-time metrics dashboard showing live routing decisions
- ✅ Statistical significance detection working

### Performance

- ✅ Redis caching: <10ms response time (measured)
- ✅ Metrics queries: 50ms → 10ms improvement (5x faster)
- ✅ API throughput: 50 → 200+ req/sec (4x improvement)

### Measurement Commands

```bash
# Test count
pytest --collect-only -q | tail -1

# Performance benchmark
ab -n 1000 -c 10 http://localhost:8000/metrics/live

# Cache hit rate
redis-cli INFO stats | grep keyspace_hits
```

---

## Risk Mitigation

### Time Risks

- **Risk**: Features take longer than estimated
- **Mitigation**: Feature 1 is highest priority, delivers immediately. Features 2-3 are additive.

### Technical Risks

- **Risk**: Redis integration complexity
- **Mitigation**: Fallback to PostgreSQL ensures zero downtime

### Integration Risks

- **Risk**: Docker Compose networking issues
- **Mitigation**: Start with local testing, Docker is last integration step

---

## Future Extensions

After this BUSU session, consider:

- Advanced ML pattern recognition with embeddings
- Full authentication and rate limiting
- Cloud deployment (RunPod when ready)
- Multi-region support
- Revenue model implementation

---

**Design Status**: Approved for implementation
**Next Step**: Set up git worktree and create implementation plan
