# model-finops

**Branch**: main | **Updated**: 2026-07-12

## Status

Vercel deploy fixed — real root cause was the project's Root Directory setting pointing at the repo root instead of `frontend/` (not the `output:'standalone'` conflict originally suspected). New `POST /api/telemetry/ingest` endpoint added so external tools (silkroute) can report usage into this dashboard without proxying through `/complete`. Repo cleanup done: dead `next-app/` and 6 stale session-artifact docs removed, ~150 files of uncommitted Prettier drift committed. Supabase currently toggled off by Tim (cost management) — turns it on as needed for demos/tests, not migrating away from it.

## Done (This Session)

- [x] Root-caused the Vercel deploy failure via real build logs (not the static-analysis guess) — Root Directory must be set to `frontend` in the Vercel dashboard
- [x] Removed dead `vercel.json`, `output:'standalone'`; fixed stale project name/URL refs in `.claude/CLAUDE.md`/`context.md`
- [x] Deleted `next-app/` (30 files, confirmed zero references from live frontend/backend) and 6 stale root docs
- [x] Committed ~150 files of pre-existing Prettier formatting drift as its own commit
- [x] New `app/routers/telemetry.py` — `POST /api/telemetry/ingest`, bearer-token auth, reuses `AsyncCostTracker.log_request()`
- [x] Extended `log_request()` with new optional columns (only included when provided — existing `/complete` callers unaffected until migration runs)
- [x] New additive migration `migrations/supabase_add_finops_ingest_columns.sql`
- [x] Verified the real HTTP contract with silkroute's client end-to-end (uvicorn + unmocked call)
- [x] Found (not fixed) a leaked Stripe webhook secret in git history (public repo, commit 98901ed, 2025-12-31) — Tim's call: deprioritized, not using Stripe currently, wants the whole integration removed as a future task
- [x] Committed as `78b4792`, `d6ff12a`, `d2b59a6`, `5d64c68`

## Blockers

None active. Backlog has 6 items logged (Stripe rotation/removal, DeepSeek/GLM/Qwen pricing verification, httpx version pin, flake8 config, test-infra TestClient mismatch).

## Tomorrow

Tomorrow: Vercel dashboard → Settings → Build & Deployment → set Root Directory = `frontend`, then push+redeploy and confirm the 4 Stripe/auth API routes resolve | Run the additive telemetry migration in Supabase SQL Editor once Supabase is turned back on | Observer notes: none run this session — reviewed inline instead; consider a dedicated cleanup session for docs/archive, docs/plans, docker-compose variants, and the Stripe removal

## Tech Stack

FastAPI + Python 3.10+ | Next.js 15/16 + Tailwind + shadcn/ui | Supabase (PostgreSQL + pgvector) | Multi-provider (Claude, Gemini, Cerebras, OpenRouter, DeepSeek, GLM, Qwen, Ollama — no OpenAI) | RunPod (backend) + Vercel (frontend)

## Session Stats

- Commits today: 5 (Vercel fix, dead-code removal, formatting pass, telemetry endpoint, + earlier end-day sync)
- Lines: +2,526 / -4,047 (net negative — this was mostly cleanup)
- Tests: full suite not runnable in dev sandbox (missing deps + no live Supabase creds) — new telemetry endpoint tests verified in isolation (5 passing) plus a real HTTP round-trip check
- Security: gitleaks run — 10 pre-existing findings, all dated Nov–Dec 2025, none from today; 1 confirmed real (Stripe webhook secret, addressed per Tim's decision above)

## Links

- GitHub: https://github.com/ScientiaCapital/model-finops
- Production: https://modelfinops.com
- Vercel project: modelfinops (scientia-capital)

---

_Updated by Vercel fix + telemetry + cleanup session. 2026-07-12._
