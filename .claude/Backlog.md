## 2026-07-12 — End Day findings

- [ ] **CRITICAL (owner: Tim, ETA: ASAP)**: Rotate Stripe webhook signing secret `whsec_Og52...` — committed to git history (commit 98901ed, 2025-12-31) of this PUBLIC repo. Not in current files. Rotate in Stripe Dashboard → Webhooks; history rewrite optional after rotation.
- [ ] Verify DeepSeek/GLM/Qwen provider pricing + endpoints once API keys exist (placeholders shipped 2026-07-11)
- [ ] Fix pre-existing test-infra rot: TestClient(app=...) starlette/httpx version mismatch breaks 129 tests in full-suite runs
