# AI Cost Optimizer - Architecture

**Version:** 4.0.0 (Supabase + Semantic Caching)
**Last Updated:** 2025-11-25

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Client Layer                                 │
│  ┌────────────┐  ┌────────────────┐  ┌──────────────────────┐   │
│  │ curl/API   │  │ Claude MCP     │  │ Next.js Dashboard    │   │
│  └─────┬──────┘  └───────┬────────┘  └──────────┬───────────┘   │
└────────┼─────────────────┼──────────────────────┼───────────────┘
         │                 │                      │
         ▼                 ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Service (18 endpoints)                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐      │
│  │ JWT Auth    │  │ Routing     │  │ Semantic Cache      │      │
│  │ (Supabase)  │  │ Engine      │  │ (pgvector)          │      │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘      │
│         │                │                     │                 │
│         ▼                ▼                     ▼                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Supabase PostgreSQL                        │    │
│  │  • pgvector for 384D embeddings                         │    │
│  │  • 18 RLS policies for multi-tenancy                    │    │
│  │  • Real-time subscriptions                              │    │
│  └─────────────────────────────────────────────────────────┘    │
│         │                                                        │
│         ▼                                                        │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │           AI Providers                                  │    │
│  │  Gemini │ Claude │ Cerebras │ OpenRouter                │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Components

### Backend (FastAPI)

| Component      | File                                 | Purpose                      |
| -------------- | ------------------------------------ | ---------------------------- |
| Main API       | `app/main.py`                        | 18 REST endpoints            |
| Auth           | `app/auth.py`                        | JWT validation, 3 auth modes |
| Routing Engine | `app/routing/engine.py`              | Strategy pattern             |
| Strategies     | `app/routing/strategy.py`            | Complexity, Learning, Hybrid |
| Semantic Cache | `app/database/cost_tracker_async.py` | pgvector caching             |
| Embeddings     | `app/embeddings/generator.py`        | sentence-transformers        |

### Frontend (Next.js 15)

| Component | File                              | Purpose         |
| --------- | --------------------------------- | --------------- |
| Dashboard | `frontend/app/dashboard/page.tsx` | Metrics display |
| API Keys  | `frontend/app/api-keys/page.tsx`  | Key management  |
| Settings  | `frontend/app/settings/page.tsx`  | Configuration   |
| API Utils | `frontend/lib/api.ts`             | Backend calls   |

---

## Routing Strategies

### HybridStrategy (Default for auto_route=true)

```
1. Query learning for recommendation
2. Check confidence:
   - HIGH → Validate against complexity, use if reasonable
   - MEDIUM/LOW → Use learning (experimental)
3. On error → Fallback to ComplexityStrategy
```

### Provider Selection

| Complexity | Provider        | Cost          |
| ---------- | --------------- | ------------- |
| Simple     | Gemini/Cerebras | FREE-$0.10/1M |
| Complex    | Claude Haiku    | $0.25/1M      |
| Fallback   | OpenRouter      | Varies        |

---

## Database Schema (Supabase)

### Core Tables

- `requests` - Request logs with embeddings
- `response_cache` - Semantic cache entries
- `routing_metrics` - Decision tracking
- `routing_feedback` - User feedback
- `experiments` - A/B test definitions

### Security

- 18 RLS policies across 7 tables
- Automatic user_id filtering
- JWT claims → Supabase context

---

## API Endpoints

| Endpoint                 | Method | Auth     | Purpose           |
| ------------------------ | ------ | -------- | ----------------- |
| `/complete`              | POST   | Optional | Route + execute   |
| `/stats`                 | GET    | Optional | Usage stats       |
| `/cache/stats`           | GET    | Optional | Cache performance |
| `/routing/metrics`       | GET    | Optional | Routing analytics |
| `/feedback`              | POST   | Optional | Submit feedback   |
| `/admin/learning/status` | GET    | Optional | ML status         |
| `/health`                | GET    | None     | Health check      |

---

## Performance

| Metric           | Value               |
| ---------------- | ------------------- |
| Cache hit rate   | 70-85% (semantic)   |
| Cold start       | ~3s (ML model load) |
| Cached request   | 50-200ms            |
| Uncached request | 500-2000ms          |

---

## Testing

```bash
pytest                     # 123 tests, 7 skipped
pytest --cov=app tests/   # Coverage report
```
