# AI Cost Optimizer - Quick Start Guide

## ✅ What We Built (v4.0.0)

Production-ready AI Cost Optimizer with:

- **Smart Routing**: Auto-selects optimal model based on complexity analysis
- **Semantic Caching**: pgvector-powered fuzzy matching (3x better cache hit rate!)
- **Multi-Tenancy**: Row-Level Security for data isolation
- **5 Providers**: Gemini (free tier), Cerebras (fast), Claude (quality), OpenRouter (fallback)
- **A/B Testing**: Built-in experiment framework for testing routing strategies
- **MCP Integration**: Works with Claude Desktop

## 🚀 Setup (10 minutes)

### 1. Prerequisites

- Python 3.10+
- Supabase account (free tier works)
- At least one AI provider API key

### 2. Configure Supabase

1. Create a new Supabase project at https://supabase.com
2. Run the SQL migrations in order:
   - `migrations/supabase_part1_extensions.sql` (enables pgvector)
   - `migrations/supabase_create_tables.sql` (creates tables)
   - `migrations/supabase_part2_schema_fixed.sql` (RLS policies)

### 3. Add Your Environment Variables

Create `.env` from the template:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```bash
# REQUIRED - Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJhbGc...
SUPABASE_SERVICE_KEY=eyJhbGc...
SUPABASE_JWT_SECRET=your-jwt-secret

# AI PROVIDERS - Pick at least ONE
GOOGLE_API_KEY=your-key          # FREE tier available - recommended to start
ANTHROPIC_API_KEY=your-key       # Best quality for complex queries
CEREBRAS_API_KEY=your-key        # Ultra-fast, cheap
OPENROUTER_API_KEY=your-key      # Fallback, access 100+ models
```

### 4. Install Dependencies

```bash
cd /Users/tmkipper/Desktop/tk_projects/ai-cost-optimizer
pip install -r requirements.txt
```

### 5. Start the Service

```bash
python app/main.py
```

You should see:

```
INFO: AI Cost Optimizer v4.0.0 initialized
INFO: Providers enabled: ['gemini', 'claude', 'cerebras']
INFO: Semantic caching: ENABLED (pgvector)
INFO: Uvicorn running on http://0.0.0.0:8000
```

### 6. Test It Works

```bash
# Test routing
curl -X POST http://localhost:8000/complete \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is AI?", "max_tokens": 100}'

# Check stats
curl http://localhost:8000/stats

# Check cache performance
curl http://localhost:8000/cache/stats
```

### 7. Add to Claude Desktop (Optional)

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ai-cost-optimizer": {
      "command": "python3",
      "args": ["/Users/tmkipper/Desktop/tk_projects/ai-cost-optimizer/mcp/server.py"],
      "env": {
        "COST_OPTIMIZER_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

Restart Claude Desktop completely (Cmd+Q, then relaunch).

## 🎯 Routing Logic

**Hybrid Strategy** (default with `auto_route=true`):

1. Learning-based recommendation from feedback data
2. Validated against complexity analysis
3. Fallback to complexity-based routing if no learning data

**Simple queries** → Gemini/Cerebras (cheapest)
**Complex queries** → Claude Haiku (best quality)

## 📊 Key Endpoints

| Endpoint                 | Method | Description                 |
| ------------------------ | ------ | --------------------------- |
| `/complete`              | POST   | Route and execute prompt    |
| `/stats`                 | GET    | Usage statistics            |
| `/cache/stats`           | GET    | Semantic cache performance  |
| `/routing/metrics`       | GET    | Routing analytics           |
| `/feedback`              | POST   | Submit quality feedback     |
| `/health`                | GET    | Service health check        |
| `/admin/learning/status` | GET    | ML learning pipeline status |

## 🔧 Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   FastAPI Service                       │
│  ┌─────────┐  ┌─────────────┐  ┌───────────────────┐   │
│  │ Routing │──│ Semantic    │──│ Supabase          │   │
│  │ Engine  │  │ Cache       │  │ PostgreSQL        │   │
│  └────┬────┘  └─────────────┘  │ + pgvector        │   │
│       │                         │ + RLS             │   │
│  ┌────▼────────────────────┐   └───────────────────┘   │
│  │ Providers: Gemini,      │                            │
│  │ Claude, Cerebras, etc.  │                            │
│  └─────────────────────────┘                            │
└─────────────────────────────────────────────────────────┘
```

## 💡 Tips

1. **Start with Gemini** - Free tier, no credit card needed
2. **Enable Semantic Caching** - Repeat queries cost $0
3. **Submit Feedback** - Improves routing over time via ML
4. **Check `/routing/metrics`** - See how routing decisions perform

## 🐛 Troubleshooting

**Service won't start:**

- Check Supabase credentials in `.env`
- Verify at least one AI provider API key is set
- Check port 8000: `lsof -i :8000`

**Cache not working:**

- Ensure pgvector extension is enabled in Supabase
- Check `migrations/supabase_part1_extensions.sql` was run

**MCP not appearing:**

- Verify absolute path in Claude Desktop config
- Check service: `curl http://localhost:8000/health`
- Completely restart Claude Desktop

## 📁 Project Structure

```
app/
├── main.py              # FastAPI service (900+ lines)
├── auth.py              # JWT authentication
├── routing/             # Strategy-based routing engine
├── database/            # Supabase async client + semantic cache
├── embeddings/          # ML embedding generator
├── learning/            # Feedback-based retraining
└── services/            # Admin & routing services

mcp/
└── server.py            # Claude Desktop integration

migrations/
├── supabase_part1_extensions.sql
├── supabase_create_tables.sql
└── supabase_part2_schema_fixed.sql
```

## 🎓 Next Steps

1. Deploy the dashboard: `cd frontend && vercel --prod`
2. Set up real-time monitoring with Supabase Realtime
3. Configure A/B tests for routing strategies
4. Review `docs/DEPLOYMENT.md` for production setup

---

Built with ❤️ using FastAPI, Supabase, and pgvector
