# CLAUDE.md — model-finops

Intelligent LLM router that reduces AI API costs by routing prompts to the most cost-efficient model — FastAPI backend with semantic caching (pgvector), multi-tenant RLS, MCP integration for Claude Desktop, and a Next.js cost dashboard.

## Stack
- Backend: FastAPI + Python 3.10+
- Frontend: Next.js 15 + Tailwind CSS + shadcn/ui
- Database: Supabase (PostgreSQL + pgvector for semantic caching)
- AI: Multi-provider — Anthropic Claude, Google Gemini, Cerebras, OpenRouter (NO OpenAI)
- Deployment: RunPod (backend) + Vercel (frontend dashboard)
- Infrastructure: Docker, MCP server for Claude Desktop

## Quick Start
```bash
./init.sh
```

## Key Files
- `app/main.py` — FastAPI entry point
- `app/routing/engine.py` — RoutingEngine with ComplexityStrategy / LearningStrategy / HybridStrategy
- `app/database/cost_tracker_async.py` — Semantic cache with 95% similarity threshold
- `app/database/supabase_client.py` — Async Supabase wrapper
- `app/embeddings/generator.py` — sentence-transformers (all-MiniLM-L6-v2, 384D)
- `app/experiments/tracker_async.py` — A/B testing framework
- `app/auth.py` — JWT auth middleware
- `mcp/server.py` — MCP server for Claude Desktop
- `frontend/` — Next.js cost dashboard
- `migrations/` — Supabase SQL migrations (pgvector, RLS)
- `requirements.txt` — Python deps

## Development
```bash
# Backend
python app/main.py
# or: uvicorn app.main:app --reload

# Frontend
cd frontend && npm run dev

# Tests
pytest tests/
```

## Environment
Requires: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`, `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`

## Policy
- No OpenAI as primary provider — Anthropic Claude or OpenRouter only
- Routing logic lives exclusively in `app/routing/`
- All cost calculations in USD cents for precision
- Provider classes must implement `send_message()` method
