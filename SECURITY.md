# Security policy

## Reporting a vulnerability

Report it through GitHub private vulnerability reporting (Security tab), or tkipper@gmail.com.
Please do not open a public issue for a vulnerability. The maintainer is Tim Kipper
(GitHub org: ScientiaCapital). This is a one-person project, so there is no response-time
guarantee.

## Supported versions

Only the current `main` branch (the `version` in `pyproject.toml`, currently 0.1.0). There are no backported fixes.

## Access control

- **Admin routes.** Every `/admin/*` route requires the `X-Admin-Key` header to match
  `ADMIN_API_KEY` (constant-time comparison, `app/auth.py`). With the variable unset, those
  routes return 503. A user token does not grant admin access.
- **`/complete`.** Requires a valid Supabase JWT by default (HS256, audience `authenticated`,
  with `exp` and `sub` claims). Anonymous use is opt-in with `ALLOW_ANONYMOUS=true`. A token
  that is present but invalid or expired is always refused with 401 on every endpoint that
  reads one, never treated as anonymous. With no `SUPABASE_JWT_SECRET` configured, a request
  that sends a token gets 503. The caller for experiment assignment and result recording is
  the token subject; a `user_id` in the request body is ignored. A prompt longer than
  `MAX_PROMPT_CHARS` (default 100000) returns 413.
- **Operator-wide read routes.** `/stats`, `/recommendation`, `/routing/metrics`,
  `/routing/decision`, `/cache/stats`, `/metrics-cache/stats`, `/quality/stats`,
  `/analytics/*` and `/insights` follow the same rule as `/complete`: a valid token, or
  `ALLOW_ANONYMOUS=true`. They read across all users, so treat any valid token as able to
  see aggregate data. Their 500 responses carry `"detail":"internal error"`.
- **Budget alert webhooks.** The three webhook URLs on `POST /budget/config` must be `https`
  and resolve only to globally routable addresses (every DNS answer is checked; a lookup
  failure refuses the URL). Loopback, private, link-local and metadata, CGNAT, unspecified
  and multicast addresses are refused, including IPv4-mapped IPv6 forms. The check runs when
  the URL is saved and again before each send, the request connects to the address that was
  checked, redirects are not followed, and each connect, read and write step times out after 5 seconds; the DNS
  lookup has no separate timeout (`app/network/ssrf.py`).
- **`/production/feedback`.** Requires a valid user token.
- **Still open to anonymous callers.** These accept requests with no user token: `/health`, `/providers`, `/docs`, `/redoc`, `/openapi.json`, `POST /feedback`, all eight `/experiments/*` routes, the `/arbitrage` model catalogue (`/arbitrage/models*`, `/arbitrage/cheapest/*`), `/billing/tiers*`, `/billing/health`, `/billing/webhook` (checked by its Stripe signature), `/forecasting/health` and the `/api/status/*` routes. The
  `/experiments/*` routes can create, complete and analyze experiments without authentication, and
  `POST /api/status/validate` sends a caller-supplied provider key to that provider. `/api/telemetry/ingest`
  uses a shared token (`FINOPS_INGEST_TOKEN`).
- **Tokenizer downloads.** `tokenizer_id` on `/complete` must be a plain Hugging Face repo id
  (`owner/name`) on an allowlist: one built-in id plus anything in `ALLOWED_TOKENIZERS`.
  Local paths and other ids return 400 before any download. At most 8 tokenizers are kept in
  memory, and downloads do not hold the shared lock. `trust_remote_code` is not enabled. No
  revision is pinned, so a listed repository can still change upstream; the `# nosec B615`
  marker in `app/tokenizer_registry.py` covers that.
- **CORS.** No origins are allowed unless `CORS_ORIGINS` names them. A bare `*` is never
  combined with credentials.
- **Semantic cache.** Reads and writes are scoped to the caller's user id, and the user id is
  part of each row's `cache_key`, so two users who send the same prompt get separate rows.
  Anonymous callers skip the cache. This has only been tested against a fake database. See
  "Known security gaps" for the live behavior that is untested.
- **Client IP.** `X-Forwarded-For` is used only when `TRUSTED_PROXY_COUNT` is above 0, and
  the chosen hop must be a valid IP address or the socket address is used instead.
  `X-Real-IP` is not used.
- **Encryption key.** Encrypting or decrypting stored provider keys raises
  `EncryptionConfigError` when `ENCRYPTION_KEY` is not set or is shorter than 32 characters.
  There is no random-key or unencrypted fallback. Decrypting with the wrong key raises a
  `ValueError` that names the likely cause.

## Known security gaps

These are true of the code today. Treat them as open.

- **The `/v1/` API-key check guards nothing.** The middleware in
  `app/middleware/api_key_auth.py` is installed for `/v1/`, but no route lives under
  `/v1/`, so API keys created through `/api-keys` are not checked by any endpoint.
- **Quota is not enforced on `/complete`.** The quota middleware needs a user id on the
  request state, which only the API-key middleware sets.
- **`mcp/server.py` sends no token.** It calls this API without an `Authorization` header, so
  against this service it needs `ALLOW_ANONYMOUS=true`.
- **`/docs`, `/redoc` and `/openapi.json` are public.** They list every route and schema.
- **Live per-user cache behavior is untested.** The cache relies on row-level security for
  the `authenticated` role and on grants in the Supabase migrations, and `set_user_context`
  is never called on the request path. None of that has been run against a real Supabase
  project, so cache lookups or writes may fail silently: failures are logged and the request
  goes to the provider uncached.
- **Row-level security is bypassed for logging on `/complete`.** Request logs and the daily
  cost total run with `user_id=None`, which uses the service-role Supabase client. Only the
  semantic cache is scoped to the user.
- **Some errors still echo detail.** Unhandled exceptions return
  `{"detail":"internal error","request_id":...}`, and the 500s of `/complete`, the operator-wide read
  routes and the Stripe webhook handler are generic, and their 400 and 503 bodies carry fixed
  validation or provider-setup text. `git grep -n
  "detail=str(e)\|detail=f" app` lists the remaining 33 sites. 20 of them return `str(e)`:
  - `app/main.py` (5): the tokenizer-not-allowed 400 and the no-provider 503 on `/complete`,
    the no-provider 503 on `/routing/decision`, and the 400 and 500 of `/feedback`
  - `app/routers/billing.py` (1), `app/routers/enterprise.py` (7),
    `app/routers/experiments.py` (4) and `app/routers/subscriptions.py` (3)

  The other 13 build the message with an f-string. Most repeat a value the caller sent (a
  capability, tier, provider or experiment id); `app/routers/arbitrage.py` line 135 includes
  the exception text. They are in `app/routers/arbitrage.py` (7), `billing.py` (2),
  `enterprise.py` (1), `experiments.py` (1) and `status.py` (2).
  The sites were not reviewed one by one. Most return messages from the service layer.

## Secret history

A Stripe webhook signing secret was committed in an earlier revision of this repository. It
has been rotated (2026-11-12), so the old value no longer works. The git history was not
rewritten, so the old value is still visible in earlier commits. CI scans the full
history with gitleaks (see below); `.gitleaksignore` lists the reviewed false positives and, separately, the fingerprint of the rotated
Stripe secret.

## Credential handling

- Credentials come from environment variables. `.env`, `.env.local` and `.env.*.local` are
  gitignored; `.env.example` holds placeholders only.
- `POST /api/telemetry/ingest` compares its bearer token to `FINOPS_INGEST_TOKEN` with
  `secrets.compare_digest` on bytes, so a non-ASCII token gets 401 (`app/routers/telemetry.py`).
- Enterprise provider keys are stored encrypted with AES-256-GCM, under a key derived with
  PBKDF2-HMAC-SHA256 (100,000 iterations) from `ENCRYPTION_KEY`
  (`app/services/encryption_service.py`). Without that variable, or with fewer than 32
  characters, the service raises instead of using a throwaway key.
- `/admin/*` compares `X-Admin-Key` to `ADMIN_API_KEY` with `hmac.compare_digest`
  (`app/auth.py`).
- Error messages for a missing model provider list environment variable names only, never
  their values (`no_provider_message()` in `app/providers.py`).

If a credential is exposed, rotate it first at the issuer (Supabase, Stripe, and each model
provider you configured), then update your `.env`. Rewriting history is optional and does not
make an exposed secret safe.

## Automated checks

CI (`.github/workflows/ci.yml`) runs on pushes to `main` and on every pull request:

- ruff lint and format check
- the test suite on Ubuntu and macOS
- pip-audit on the locked dependencies
- bandit at medium severity and above on `app/`
- gitleaks over the full git history
- a check that `requirements.txt` and `requirements-embeddings.txt` match `uv.lock`
- a Docker build with no push (the default image, without the embeddings extra)

To scan locally: `gitleaks git --redact -v .`

## Data handling

See the Data handling section of [README.md](README.md) for what is stored and which
third parties receive prompts.
