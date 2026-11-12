# model-finops

[![ci](https://github.com/ScientiaCapital/model-finops/actions/workflows/ci.yml/badge.svg)](https://github.com/ScientiaCapital/model-finops/actions/workflows/ci.yml)
![python](https://img.shields.io/badge/python-3.12%2B-blue)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)
![status](https://img.shields.io/badge/status-v0.1.0-lightgrey)

[What you get](#what-you-get) · [Quick start](#quick-start) · [Configuration](#configuration) · [Design decisions](#design-decisions) · [Status](#status) · [Data handling](#data-handling) · [License](#license)

model-finops is a FastAPI service that sends an LLM prompt to one of several provider APIs and
records the token counts and cost of each call in Supabase. By default it picks the provider
from a score built from the prompt's length and keywords; with `auto_route` set it uses
per-pattern history from a local SQLite file and, when there is no history, falls back to the
complexity tier's pick among the providers you have configured. Responses are cached per
user by embedding similarity in Postgres (pgvector). The same service exposes routers for
budgets, cost forecasting, A/B routing experiments, API-key management (create, list and
revoke keys; see the note on `/v1/` below), enterprise provider-key tracking, SaaS subscription tracking, Stripe billing, and a
token-authenticated endpoint where other tools can report usage they already measured.

## What you get

| Piece | Where | Tested here |
| --- | --- | --- |
| HTTP API: `/complete`, `/stats`, `/providers`, `/routing/*`, `/analytics/*`, `/budget/*`, feedback and admin endpoints | `app/main.py` | Partly: `/complete` input validation and auth, `/routing/metrics` with a mocked cache, `/production/feedback` and `/admin/*` access control; the Supabase-backed endpoints are integration tests |
| Routers: arbitrage, enterprise, forecasting, experiments, subscriptions, telemetry | `app/routers/` | Yes, with Supabase mocked |
| Routers: billing (Stripe), API keys, provider status | `app/routers/` | Stripe webhook error handling only |
| Routing engine: complexity and hybrid strategies | `app/routing/` | Yes |
| 14 provider adapters: Gemini, Claude, OpenRouter, Cerebras, Groq, Together AI, Mistral, Fireworks, Cohere, Ollama, Bedrock, DeepSeek, GLM, Qwen | `app/providers.py` | 8 of 14. Seven mock the HTTP client; Bedrock mocks the boto3 client, not HTTP |
| Semantic response cache (sentence-transformers embeddings, pgvector match) | `app/database/cost_tracker_async.py`, `app/embeddings/generator.py` | Partly: `tests/test_semantic_caching.py` (25 tests, with mocks; the ones that need a live Supabase are skipped) and `tests/test_cache_without_embeddings.py` (4 tests); `tests/test_cache_isolation.py` checks that one user never gets another user's entry. The pgvector match itself needs a live Supabase project |
| Supabase schema and row-level security policies | `supabase/migrations/` | No |
| MCP server that forwards Claude Desktop tool calls to this API | `mcp/server.py` | No |
| Next.js dashboard | `frontend/` | No, not built in this pass |
| Standalone LangGraph cost-tracking package | `packages/langgraph-cost-optimizer/` | No, not run in this pass |

## Quick start

Needs [uv](https://docs.astral.sh/uv/). No provider keys and no Supabase project are needed
for the tests.

```bash
git clone https://github.com/ScientiaCapital/model-finops.git
cd model-finops
uv sync --frozen
uv run --frozen python -m pytest -q
```

To run the service without any external accounts (the Supabase values are placeholders; the
client is created at import time but does not connect until a request needs it). The
`env -u` and `OLLAMA_HOST` parts make sure no real key or local Ollama server is picked up
from your shell. `SUPABASE_JWT_SECRET` is the secret that verifies caller tokens; use any
string of 32 or more characters here:

```bash
env -u ANTHROPIC_API_KEY OLLAMA_HOST=http://127.0.0.1:9 \
  SUPABASE_URL=http://127.0.0.1:9 SUPABASE_ANON_KEY=placeholder \
  SUPABASE_JWT_SECRET=dev-only-secret-at-least-32-bytes-long \
  uv run --frozen uvicorn app.main:app --port 8000

curl -i localhost:8000/health
curl -i "localhost:8000/routing/decision?prompt=What%20is%20Python"
curl -i -X POST localhost:8000/complete -H 'content-type: application/json' \
  -d '{"prompt":"What is Python"}'
```

With no provider configured, `/health` returns 200 with `"providers_available":[]`.
`/routing/decision` and `POST /complete` return 401 `{"detail":"Authentication required"}`
without a token, because they need a valid Supabase JWT by default. With a valid token (or
`ALLOW_ANONYMOUS=true`) both return 503 with a JSON `detail` that names the variables to set
(`GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY` and so on, a running Ollama server, or
AWS credentials). A reachable local Ollama server counts as a configured provider.

To call `/complete` with a token, sign one with the same secret (any user id works locally):

```bash
TOKEN=$(SUPABASE_JWT_SECRET=dev-only-secret-at-least-32-bytes-long uv run --frozen python -c "
import os, time, jwt
print(jwt.encode({'sub': 'demo-user', 'aud': 'authenticated', 'exp': int(time.time()) + 3600},
                 os.environ['SUPABASE_JWT_SECRET'], algorithm='HS256'))")

curl -i -X POST localhost:8000/complete -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' -d '{"prompt":"What is Python"}'
```

With no provider configured this returns 503 with the same provider message. A token that is
present but invalid or expired returns 401 on every endpoint that reads one. To try the API
without tokens, start the server with `ALLOW_ANONYMOUS=true`; anonymous requests then reach
the router but get no semantic cache.

Setting one provider key changes that. This does not call the provider; the key is only
checked for presence at startup:

```bash
env -u ANTHROPIC_API_KEY OLLAMA_HOST=http://127.0.0.1:9 GROQ_API_KEY=placeholder \
  SUPABASE_URL=http://127.0.0.1:9 SUPABASE_ANON_KEY=placeholder \
  uv run --frozen uvicorn app.main:app --port 8000

curl localhost:8000/health
# {"status":"healthy","providers_available":["groq"],...,"version":"0.1.0"}
```

`/routing/decision`, called with a token (or `ALLOW_ANONYMOUS=true`), then returns 200 and picks only
from the configured providers.
`POST /complete` (with a token, as above) makes a real provider call, and then needs a
reachable Supabase project (see Known gaps). `.env.example` lists the provider and Supabase
variables.

### Semantic cache and the embeddings extra

The semantic cache needs the optional `embeddings` extra (`uv sync --frozen --extra embeddings`,
which pulls in torch). Without it:

- At startup the app logs a WARNING from the embedding generator, `Model warmup failed:
  sentence-transformers is required for semantic caching ...`, followed by a WARNING from
  `app/main.py`, `Embedding model not available`. The service still starts.
- Cache reads and writes are skipped and every request goes to the provider. There is no
  exact-match fallback.
- The first skipped cache call on a tracker logs one INFO line, `semantic cache disabled:
  sentence-transformers is not installed`; later skips on that tracker log at DEBUG. A new
  tracker is created for each signed-in request, so that INFO line can appear once per request.

### Docker

The default image does not include the embeddings extra, so it stays small (803 MB, measured with `docker images` on linux/arm64):

```bash
docker build -t model-finops .
docker run --rm -p 8000:8000 -e PORT=8000 \
  -e SUPABASE_URL=https://example.supabase.co -e SUPABASE_ANON_KEY=placeholder \
  -e SUPABASE_JWT_SECRET=dev-only-secret-at-least-32-bytes-long model-finops
```

To include semantic-cache embeddings, build with `WITH_EMBEDDINGS=1`. That installs CPU-only
PyTorch first and leaves out the NVIDIA CUDA packages (2.23 GB, measured the same way):

```bash
docker build --build-arg WITH_EMBEDDINGS=1 -t model-finops .
```

`requirements.txt` is the default install and `requirements-embeddings.txt` adds the extra. Both
are generated from `uv.lock` by `make requirements`, and CI checks that they match.

## Configuration

Security-relevant settings. `.env.example` has the full list, including provider and Supabase
variables.

| Variable | Default | Effect |
| --- | --- | --- |
| `SUPABASE_JWT_SECRET` | unset | Secret that verifies caller tokens (HS256, audience `authenticated`). A token must carry `exp` and `sub`. With no secret set, a request that sends a token gets 503 `Server authentication configuration error`. |
| `ALLOW_ANONYMOUS` | `false` | `POST /complete` and the operator-wide read routes (`/stats`, `/recommendation`, `/routing/*`, `/cache/stats`, `/metrics-cache/stats`, `/quality/stats`, `/analytics/*`, `/insights`) return 401 without a valid token. Set to `true` or `1` to accept requests with no `Authorization` header. A header that is present but invalid is always 401. Anonymous requests get no semantic cache. `/health` is always public. |
| `ADMIN_API_KEY` | unset | Required for every `/admin/*` route, sent as the `X-Admin-Key` header and compared in constant time. When unset those routes return 503; they are never open. A wrong or missing key returns 401. |
| `ALLOWED_TOKENIZERS` | empty | Comma-separated Hugging Face repo ids (`owner/name`) that `tokenizer_id` may name, in addition to the built-in `UW/OLMo2-8B-SuperBPE-t180k`. Anything else, including local paths, returns 400. |
| `CORS_ORIGINS` | empty | Comma-separated allowed origins. Empty means no cross-origin access. Origins listed here may send credentials. A bare `*` is allowed but never combined with credentials. |
| `ENCRYPTION_KEY` | unset | Key for encrypting stored provider keys, at least 32 characters. With no key, or a shorter one, encrypting or decrypting raises `EncryptionConfigError`; there is no fallback. Decrypting with a different key raises a `ValueError` that says so. Generate one with `python -c "import secrets; print(secrets.token_hex(32))"`. |
| `TRUSTED_PROXY_COUNT` | `0` | Number of trusted reverse proxies in front of the app. At `0` the `X-Forwarded-For` header is ignored when logging API-key usage and the socket address is used; above `0` the client IP is taken from `X-Forwarded-For`, counted from the right; a hop that is not a valid IP address is ignored and the socket address is used. `X-Real-IP` is never used. |
| `MAX_PROMPT_CHARS` | `100000` | Longest `prompt` that `POST /complete` accepts, in characters. A longer prompt returns 413 before any routing or provider call. An unset, empty, non-numeric or non-positive value means the default. |
| `FINOPS_INGEST_TOKEN` | unset | Bearer token for `/api/telemetry/ingest`, compared with `secrets.compare_digest`. Unset means every request to that route gets 401. |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Model for the semantic cache. The database columns are 384-dimensional, so a replacement must also produce 384 dimensions. |

`POST /production/feedback` requires a valid user token. `POST /complete` uses the subject of
that token as the caller for experiment assignment and result recording; a `user_id` in the
request body is accepted for compatibility and ignored.

Budget alert webhooks (`alert_webhook_url`, `slack_webhook_url`, `discord_webhook_url` on
`POST /budget/config`) must be `https` URLs whose host resolves only to public addresses.
Loopback, private, link-local (including cloud metadata addresses), CGNAT and unspecified
addresses are refused with 400 when the URL is saved and again when an alert is sent. Alerts
connect to the address that was checked, time out after 5 seconds on each connect, read and write
step (the DNS lookup has no separate timeout) and do not follow redirects
(`app/network/ssrf.py`). The version reported by `/health`
and in the OpenAPI document is the `version` in `pyproject.toml`, read from installed package
metadata when present and from `pyproject.toml` itself otherwise.

The `/v1/` API-key middleware (`app/middleware/api_key_auth.py`) is installed, but no route
lives under `/v1/`, so no endpoint currently requires an API key. The API-key endpoints under
`/api-keys` create and manage keys that nothing yet checks.

## Design decisions

- **Two routing modes behind one flag.** `auto_route=false` scores the prompt from word count
  (up to 0.5) plus matched keywords (0.3 each, capped at 0.5) and maps below 0.3, below 0.7
  and the rest to three model tiers. `auto_route=true` uses the hybrid strategy: a
  high-confidence pick from history is kept only if it is within one tier of the complexity
  pick, lower-confidence picks are returned marked `experimental`, and with no history it
  returns the complexity tier's pick among the providers that are available (Gemini Flash,
  Claude Haiku or Claude Sonnet when those are configured, otherwise another available
  provider). Implemented in `app/routing/complexity.py`,
  `app/routing/strategy.py` and `app/routing/engine.py`.
- **Providers are enabled by environment.** An adapter is registered only when its key is
  set; Ollama is registered when a local server answers, Bedrock when AWS credentials are
  set (it also needs `boto3`, which this project does not install), and OpenRouter last. Routing chooses only among the registered providers; with none
  registered, `/complete` and `/routing/decision` return 503 and name the variables to set.
  Implemented in `app/providers.py` (`PROVIDER_REGISTRY`, `no_provider_message`,
  `init_providers`) and `app/services/routing_service.py` (`_decide`).
- **Cache on meaning, not exact text, per user.** Prompts are embedded locally with
  `all-MiniLM-L6-v2` by default (384 dimensions; set `EMBEDDING_MODEL` to use another
  384-dimension model; needs the `embeddings` extra, otherwise the cache is skipped) and
  matched in Postgres through the `match_cache_entries` function at a default similarity of
  0.95. (`match_cache_entries_v2` is called only when metadata filters are passed, and the
  cache path never passes any.) Lookups and writes carry the caller's user id, the user id is
  part of each row's `cache_key`, and anonymous callers skip the cache, so one user never
  receives another user's cached response and two users with the same prompt get separate
  rows. Implemented in
  `app/database/cost_tracker_async.py` and `app/database/supabase_client.py`.
- **Separate auth for machine-reported usage.** `POST /api/telemetry/ingest` takes a bearer
  token compared with `secrets.compare_digest` against `FINOPS_INGEST_TOKEN`, so other tools
  can log usage without a Supabase user session. Implemented in `app/routers/telemetry.py`.
- **Provider keys encrypted at rest.** Enterprise provider keys are encrypted with AES-256-GCM
  under a key derived by PBKDF2-HMAC-SHA256 (100,000 iterations) from `ENCRYPTION_KEY`, and
  refuse to run when that variable is missing. Implemented in `app/services/encryption_service.py`.

## Status

Built and tested (offline, Python 3.12, `uv sync --frozen`): **765 passed, 45 skipped**.
The 45 skips are tests that need a live Supabase project (37; 24 of them opt in with
`RUN_INTEGRATION=1` plus real credentials), tests disabled because their mocks do not work (4),
tests that need a PostgreSQL `TEST_DATABASE_URL` (3), and one that needs a 30-second wait. CI runs ruff, the test suite on Ubuntu and macOS, pip-audit, bandit,
gitleaks over full history, and a Docker build.

Not tested here:

- Gemini, Claude, OpenRouter, Cerebras, Groq and Together AI adapters have no offline tests.
- Sending a budget alert to a real Slack or Discord endpoint (the webhook address checks are tested with a fake resolver and transport), Stripe billing calls, the MCP server, the
  frontend and `packages/langgraph-cost-optimizer` have no tests in this suite.
- The pgvector match and the analytics endpoints run only against a live Supabase project;
  the cache logic around them is tested with mocks.

Known gaps in the code:

- Once a provider is configured, `POST /complete` still needs a reachable Supabase project.
  A failed cache write is logged and skipped, and the response is returned uncached. A failed
  request log or daily cost total returns HTTP 500.
- A request that names an unknown or unconfigured provider returns HTTP 500, not 400
  (`app/services/routing_service.py` raises `ValueError`, and `/complete` has no handler for
  it, so it reaches the generic 500 handler).
- The MCP server (`mcp/server.py`) sends no `Authorization` header. Against this service it
  needs `ALLOW_ANONYMOUS=true`, which also means no semantic cache for those calls.
- Monthly quota is not enforced for `/complete`. The quota middleware reads a user id from
  request state, and only the API-key middleware sets one.
- The `/v1/` API-key middleware guards no route, because nothing lives under `/v1/`.
- Request logs and the daily cost total on `/complete` still use the service-role Supabase
  client with no user id, so they are not attributed to the caller. Only the semantic cache
  is scoped to the user.
- The per-user semantic cache has not been run against a real Supabase project. It relies on
  row-level security with the `authenticated` role, and the code never calls
  `set_user_context`, so lookups and writes may fail silently (they are logged and the request
  goes to the provider). The tests use a fake database.
- These routes accept requests with no user token: `/health`, `/providers`, `/docs`, `/redoc`, `/openapi.json`, `POST /feedback`, all eight `/experiments/*` routes, the `/arbitrage` model catalogue (`/arbitrage/models*`, `/arbitrage/cheapest/*`), `/billing/tiers*`, `/billing/health`, `/billing/webhook` (checked by its Stripe signature), `/forecasting/health` and the `/api/status/*` routes. `POST /api/status/validate`
  sends a caller-supplied key to the provider. `/api/telemetry/ingest` uses a shared token. The
  `/experiments/*` routes can create and complete experiments without authentication.
- Some endpoints still return exception text or caller input in the `detail` of a 400, 404,
  500 or 503 body. `SECURITY.md` lists them. Unhandled exceptions, and the 500s of `/complete`, the
  operator-wide read routes and the Stripe webhook, return generic messages; their 400 and 503 bodies
  carry fixed validation or provider-setup text.

Not measured: cost savings, cache hit rate and latency. No benchmark results are published
in this repository.

## Data handling

- Each logged request stores the first 100 characters of the prompt, provider, model,
  token counts, cost and user id in the Supabase `requests` table.
- Each cached response stores the normalized full prompt, the full response and its
  embedding in `response_cache`.
- Prompts are sent to whichever third-party provider the router picks. Embeddings are
  computed in-process; no embedding API is called.
- Row-level security is enabled on the main tables (`supabase/migrations/`), but request
  logging and the daily cost total on `/complete` run with `user_id=None`, which uses the
  service-role client and bypasses it. The cache for a signed-in caller uses the
  user-scoped client and filters by that user id.
- `CORS_ORIGINS` defaults to empty, which allows no cross-origin access; set it to the origins
  that need it.
- `.env` files are gitignored. Credential handling rules are in `SECURITY.md`.

## License

MIT. See [LICENSE](LICENSE). Copyright (c) 2025-2026 Tim Kipper.
