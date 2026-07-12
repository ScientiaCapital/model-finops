## 2026-07-12 — End Day findings

- [ ] Rotate Stripe webhook signing secret `whsec_Og52...` whenever convenient — committed to git history (commit 98901ed, 2025-12-31) of this PUBLIC repo, not in current files. Tim's call 2026-07-12: not actively using Stripe right now, deprioritized from CRITICAL — still cheap insurance if the webhook endpoint is still live in the Stripe dashboard.
- [ ] Remove unused Stripe integration entirely (Tim, 2026-07-12: not currently using Stripe) — `app/billing/stripe_client.py`, `app/services/billing_service.py`, `app/routers/billing.py`, `frontend/lib/stripe/`, `frontend/app/api/stripe/*`, `frontend/app/billing/`, `frontend/app/pricing/`. Needs its own scoping pass — check what else (subscriptions, enterprise tiers) depends on billing_service before removing.
- [ ] Verify DeepSeek/GLM/Qwen provider pricing + endpoints once API keys exist (placeholders shipped 2026-07-11)
- [ ] Fix pre-existing test-infra rot: TestClient(app=...) starlette/httpx version mismatch breaks 129 tests in full-suite runs
- [ ] Pin `httpx>=0.27.0,<0.28` in requirements.txt (found 2026-07-12 while testing the new telemetry endpoint — httpx 0.28 removed the `app=` kwarg this repo's TestClient still needs)
- [ ] Fix broken flake8 config — invalid `ignore` entry crashes flake8 before it can lint (found 2026-07-12)
