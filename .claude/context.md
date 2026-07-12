# AI Cost Optimizer - Project Context

Last Updated: 2025-11-25
Session: Backend Deployment + Testing

## 📊 Current Status: v4.0.0 Production Ready

### Live URLs

- **Dashboard**: https://modelfinops.com
- **Backend API**: `https://YOUR_POD_ID-8000.proxy.runpod.net` (RunPod)
- **Docker Image**: `ghcr.io/scientiacapital/ai-cost-optimizer:latest`
- **GitHub**: https://github.com/ScientiaCapital/model-finops
- **Vercel Project**: modelfinops (scientia-capital) — Root Directory MUST be set to `frontend`

### Tech Stack

- **Backend**: FastAPI + Supabase PostgreSQL + pgvector
- **Frontend**: Next.js 15 + React 19 + Tailwind CSS + Shadcn/ui
- **Auth**: Supabase JWT with Row-Level Security
- **Caching**: Semantic caching (sentence-transformers, 384D embeddings)
- **CI/CD**: GitHub Actions → GHCR → RunPod
- **Tests**: 123 passing, 7 skipped

### Platform Constraint

- **Development**: Apple Silicon (M1/M2/M3) - ARM64 architecture
- **Production**: RunPod - x86_64/amd64 architecture
- **Solution**: GitHub Actions builds linux/amd64 images automatically

---

## ✅ Completed Today (2025-11-25)

### Session 1: Frontend Dashboard + Cleanup

1. **Git Hygiene** - Committed 4 modified files, added GITHUB_ABOUT.md
2. **Codebase Cleanup** - Removed 28 legacy files (SQLite, old scripts)
3. **Tests Fixed** - All 123 tests passing (7 skipped)
4. **Documentation Updated** - QUICK-START.md, WHATS-BUILT.md, CLAUDE.md
5. **Frontend Dashboard Built** - Next.js 15 + Shadcn/ui, deployed to Vercel

### Session 2: Backend Deployment (In Progress)

1. **GitHub Actions Workflow** - Created `.github/workflows/docker-build.yml`
   - Builds linux/amd64 images for RunPod compatibility
   - Pushes to GHCR (ghcr.io/scientiacapital/ai-cost-optimizer)
   - Triggers on push to main (app/**, requirements.txt, Dockerfile)
2. **Documentation** - Added Apple Silicon + RunPod deployment docs to CLAUDE.md

---

## 📁 Project Structure

```
ai-cost-optimizer/
├── .github/workflows/     # CI/CD
│   └── docker-build.yml   # Build & push to GHCR
├── app/                   # FastAPI backend
│   ├── main.py           # 18 REST endpoints
│   ├── auth.py           # JWT authentication
│   ├── routing/          # Strategy-based routing
│   ├── database/         # Supabase client + semantic cache
│   └── embeddings/       # ML embedding generator
├── frontend/             # Next.js dashboard
│   ├── app/              # App Router pages
│   ├── components/       # UI components
│   └── lib/              # API + Supabase utilities
├── mcp/                  # Claude Desktop integration
├── migrations/           # Supabase SQL
└── tests/                # 123 passing tests
```

---

## 🔧 Environment Variables

### Backend (.env)

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJhbGc...
SUPABASE_SERVICE_KEY=eyJhbGc...
SUPABASE_JWT_SECRET=your-jwt-secret
GOOGLE_API_KEY=...
ANTHROPIC_API_KEY=...
```

### Frontend (Vercel Dashboard)

```
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
NEXT_PUBLIC_API_URL=...
```

---

## 🎯 Next Steps

### Immediate (This Session)

1. ⏳ Trigger GitHub Actions workflow (manual run)
2. ⏳ Deploy to RunPod with env vars
3. ⏳ Update Vercel `NEXT_PUBLIC_API_URL` to RunPod endpoint
4. ⏳ Test dashboard with live backend

### Monetization Phase (Future)

1. Stripe integration for billing
2. Usage tracking & quotas
3. Landing page with ROI calculator
4. Self-service signup flow

---

## 📝 Notes for Next Session

- Backend deployed to RunPod (update URL above once live)
- GPU upgrade: just change `EMBEDDING_DEVICE=cpu` → `cuda`
- First request may be slow (40-60s) while ML model downloads
- Consider beta customer outreach once stable
