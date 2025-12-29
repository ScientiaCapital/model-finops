# CLAUDE.md - AI Cost Optimizer

## Start Day Protocol

When user says "start day":
1. Read CLAUDE.md
2. `git status` + `git log --oneline -5`
3. List blockers and next 3 priorities

---

## 1. Project Status & Overview

**Current Status**: Supabase Migration Complete! 🚀✨
**Version**: 4.0.0 (Supabase + Semantic Caching + Multi-Tenant)
**Type**: Multi-Tenant AI/ML Cost Optimization Service with Semantic Caching

The AI Cost Optimizer is a production-ready FastAPI service that intelligently routes LLM prompts to optimal AI models using **semantic caching**, **multi-tenant RLS**, and **async-first architecture**. It serves as both a standalone API and an MCP (Model Context Protocol) server for Claude Desktop integration.

**🎉 MAJOR UPGRADE - Supabase Migration** (COMPLETE!):
- ✅ **Semantic Caching**: pgvector-powered fuzzy matching (3x better cache hit rate!)
- ✅ **Multi-Tenancy**: Row-Level Security (RLS) for data isolation
- ✅ **Async-First**: All database operations non-blocking
- ✅ **Managed PostgreSQL**: Supabase replaces SQLite + Redis
- ✅ **Real-time Subscriptions**: Supabase Realtime (replaces custom WebSocket)
- ✅ **JWT Authentication**: Secure user authentication with automatic RLS
- ✅ **ML Embeddings**: Local 384D vectors (sentence-transformers)

**Previous Features** (Still Active):
- ✅ **A/B Testing Framework**: Experiment tracking with statistical analysis
- ✅ **Intelligent Auto-Routing**: Learning-based model selection with hybrid validation
- ✅ **Strategy Pattern Architecture**: Pluggable routing strategies (complexity, learning, hybrid)
- ✅ **Metrics & Analytics**: Comprehensive routing performance tracking and ROI analysis

**Core Features**:
- Multi-provider support (Gemini, Claude, Cerebras, OpenRouter)
- Semantic caching with 95% similarity threshold (fuzzy matching!)
- Multi-tenant user isolation via RLS
- Real-time metrics streaming via Supabase Realtime
- JWT-based authentication
- Claude Desktop MCP integration
- Fallback routing for reliability

## 2. Technology Stack

### Core Framework & Runtime
- **Language**: Python 3.8+
- **Web Framework**: FastAPI (with automatic OpenAPI docs)
- **ASGI Server**: Uvicorn with standard extras
- **Environment Management**: python-dotenv

### Database & Backend (Supabase Platform)
- **Database**: Supabase PostgreSQL (managed, production-ready)
- **Vector Extension**: pgvector for 384D embeddings (IVFFlat indexing)
- **Authentication**: Supabase Auth with JWT (HS256)
- **Row-Level Security**: 18 RLS policies across 7 tables for multi-tenancy
- **Real-time**: Supabase Realtime for live metrics streaming
- **Python Client**: supabase-py>=2.3.0
- **Data Validation**: Pydantic v2
- **HTTP Client**: httpx for async API calls

### AI/ML Components
- **Primary Providers**: Google Gemini, Anthropic Claude, Cerebras, OpenRouter
- **Embeddings**: sentence-transformers (all-MiniLM-L6-v2, 384 dimensions)
- **ML Framework**: PyTorch (GPU/CPU auto-detection)
- **Semantic Search**: Cosine similarity with 95% threshold
- **RoutingEngine**: Strategy pattern-based routing orchestrator
  - **ComplexityStrategy**: Keyword + length-based scoring (baseline)
  - **LearningStrategy**: Learning-based recommendations from performance data
  - **HybridStrategy**: Learning with complexity validation (default for auto_route=true)
- **MetricsCollector**: Async tracking of routing decisions, costs, confidence levels
- **ExperimentTracker**: A/B testing with deterministic user assignment
- **Token Counting**: Custom token estimation logic

### Development & Testing
- **Testing**: pytest with asyncio support
- **Containerization**: Docker & Docker Compose
- **Migrations**: Supabase SQL migrations
- **Code Quality**: Pre-commit hooks (if configured)

## 3. Development Workflow

### Initial Setup
```bash
# Clone and setup
git clone <repository>
cd ai-cost-optimizer

# Environment setup
cp .env.example .env
# Edit .env with your Supabase credentials and API keys:
#   - SUPABASE_URL=https://your-project.supabase.co
#   - SUPABASE_ANON_KEY=eyJhbGc...
#   - SUPABASE_SERVICE_KEY=eyJhbGc...
#   - SUPABASE_JWT_SECRET=your-jwt-secret
#   - GOOGLE_API_KEY, ANTHROPIC_API_KEY, etc.

# Install dependencies (includes ML models)
pip install -r requirements.txt
pip install -r mcp/requirements.txt

# Run database migrations (via Supabase SQL Editor)
# 1. Go to https://supabase.com/dashboard/project/YOUR_PROJECT/sql
# 2. Run migrations/supabase_part1_extensions.sql
# 3. Run migrations/supabase_create_tables.sql
# 4. Run migrations/supabase_part2_schema_fixed.sql
```

### Running the Application

**Development Mode**:
```bash
# Run FastAPI with auto-reload
python app/main.py
# or
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Production Mode**:
```bash
# Using Docker
docker-compose up --build

# Or directly
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app tests/

# Run specific test file
pytest tests/test_routing.py -v
```

### Building & Deployment
```bash
# Build Docker image
docker build -t ai-cost-optimizer .

# Run with Docker
docker run -p 8000:8000 --env-file .env ai-cost-optimizer
```

## 4. Environment Variables

Create a `.env` file with:

### Required - Supabase Configuration
```env
# Supabase Backend (REQUIRED)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJhbGc...  # Public anon key (respects RLS)
SUPABASE_SERVICE_KEY=eyJhbGc...  # Admin service key (bypasses RLS)
SUPABASE_JWT_SECRET=your-jwt-secret  # For JWT validation
SUPABASE_DB_PASSWORD=your-db-password  # Database password
```

### Required - AI Provider Keys (at least one)
```env
# Gemini (Recommended for free tier)
GOOGLE_API_KEY=your_gemini_key

# Anthropic Claude
ANTHROPIC_API_KEY=your_claude_key

# OpenRouter (Fallback)
OPENROUTER_API_KEY=your_openrouter_key

# Cerebras (Optional)
CEREBRAS_API_KEY=your_cerebras_key
```

### Optional Configuration
```env
# Service Configuration
COST_OPTIMIZER_API_URL=http://localhost:8000
LOG_LEVEL=INFO

# MCP Server (for Claude Desktop)
MCP_SERVER_PORT=8001

# Embedding Configuration
EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DEVICE=cpu  # or 'cuda' for GPU
SIMILARITY_THRESHOLD=0.95  # Cache hit threshold (0-1)
```

## 5. Key Files & Their Purposes

### Core Application
- `app/main.py` - FastAPI application entry point, route definitions, lifespan management
- `app/auth.py` - JWT authentication middleware and dependencies (170 lines)
- `app/routing/` - Prompt analysis and model routing logic
  - `app/routing/engine.py` - RoutingEngine with strategy pattern
  - `app/routing/metrics_async.py` - AsyncMetricsCollector (350 lines)
- `app/providers/` - API clients for different LLM providers
- `app/services/routing_service.py` - High-level routing orchestration (async)
- `app/models/` - Pydantic models for request/response schemas

### Database & Backend (Supabase)
- `app/database/supabase_client.py` - Async Supabase client wrapper (350 lines)
- `app/database/cost_tracker_async.py` - AsyncCostTracker with semantic caching (900+ lines)
- `app/embeddings/generator.py` - EmbeddingGenerator using sentence-transformers (280 lines)
- `app/experiments/tracker_async.py` - AsyncExperimentTracker for A/B testing (450 lines)
- `migrations/supabase_part1_extensions.sql` - pgvector, extensions, RPC functions
- `migrations/supabase_create_tables.sql` - 9 table definitions
- `migrations/supabase_part2_schema_fixed.sql` - RLS policies (18 policies across 7 tables)

### MCP Integration
- `mcp/server.py` - MCP server implementation for Claude Desktop
- `mcp/requirements.txt` - MCP-specific dependencies

### Configuration & Deployment
- `requirements.txt` - Main application dependencies (includes Supabase, ML libs)
- `Dockerfile` - Containerization configuration
- `docker-compose.yml` - Multi-service setup
- `.env.example` - Environment template with Supabase configuration

### Documentation
- `.claude/CLAUDE.md` - This file (project overview for AI assistants)
- `docs/REALTIME_SETUP.md` - Guide for Supabase Realtime integration (400+ lines)

### Testing
- `tests/` - Test suite with unit and integration tests
- `tests/conftest.py` - Shared pytest fixtures for Supabase
- `tests/test_routing.py` - Routing logic tests
- `tests/test_providers.py` - Provider API tests
- `tests/test_experiment_*.py` - A/B testing framework tests
- `tests/test_metrics_*.py` - Metrics collection and caching tests

## 6. Testing Approach

### Test Structure
```python
# Example test pattern
def test_prompt_routing_simple():
    """Test that simple prompts route to Gemini"""
    prompt = "Hello, how are you?"
    result = router.analyze_prompt(prompt)
    assert result.provider == "gemini"
    assert result.is_complex == False

def test_provider_fallback():
    """Test fallback behavior when primary provider fails"""
    # Mock primary provider to fail
    # Verify fallback to OpenRouter
```

### Running Tests
```bash
# Complete test suite
pytest

# Specific test category
pytest tests/test_routing.py
pytest tests/test_providers.py

# With verbose output
pytest -v --tb=short

# Test coverage report
pytest --cov=app --cov-report=html
```

### Test Data
- Mock API responses for providers
- Sample prompts of varying complexity
- Database state management with fixtures

## 7. Deployment

### Backend (FastAPI)
```bash
# Local development
python app/main.py

# Docker
docker-compose up --build
```

### Frontend (Next.js Dashboard)
- **Production URL**: https://ai-cost-optimizer-scientia-capital.vercel.app
- **Vercel Project**: ai-cost-optimizer (scientia-capital)
- **Stack**: Next.js 15, React 19, Tailwind CSS, Shadcn/ui

```bash
cd frontend
npm run dev      # Local development
vercel --prod    # Deploy to production
```

### Environment Variables (Vercel Dashboard)
```
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGc...
NEXT_PUBLIC_API_URL=https://YOUR_POD_ID-8000.proxy.runpod.net
```

### Apple Silicon Build Instructions

**Important**: Apple Silicon Macs (M1/M2/M3) use ARM64 architecture, but RunPod uses x86_64/amd64. You cannot build Docker images locally that will run on RunPod.

**Solution 1: GitHub Actions (Recommended)**

Push to main branch to trigger automatic build:
```bash
git push origin main
# Workflow triggers on changes to: app/**, requirements.txt, Dockerfile
# Manual trigger: Go to GitHub Actions → Run workflow
```

Image pushed to: `ghcr.io/scientiacapital/ai-cost-optimizer:latest`

**Solution 2: Manual buildx (One-off builds)**
```bash
# Setup buildx (one-time)
docker buildx create --use --name multiarch

# Build and push for linux/amd64 (GHCR)
docker buildx build --platform linux/amd64 --push \
  -t ghcr.io/scientiacapital/ai-cost-optimizer:latest .

# Or push to Docker Hub (username: tmk74)
docker buildx build --platform linux/amd64 --push \
  -t docker.io/tmk74/ai-cost-optimizer:latest .
```

### Docker Registry Options
- **GHCR**: `ghcr.io/scientiacapital/ai-cost-optimizer:latest`
- **Docker Hub**: `docker.io/tmk74/ai-cost-optimizer:latest` (username: `tmk74`)

### RunPod Deployment

**Pod Configuration**:
- Container Image: `ghcr.io/scientiacapital/ai-cost-optimizer:latest`
- Container Disk: 20GB
- Volume Disk: 10GB (mount to `/app/model_cache`)
- Expose Port: 8000
- GPU: None for testing (~$0.10/hr), RTX 4090 for production (~$0.74/hr)

**Environment Variables (RunPod Dashboard)**:
```
# Required
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJhbGc...
SUPABASE_SERVICE_KEY=eyJhbGc...
SUPABASE_JWT_SECRET=your-jwt-secret
GOOGLE_API_KEY=your-key
ANTHROPIC_API_KEY=your-key

# Configuration
PORT=8000
LOG_LEVEL=INFO
EMBEDDING_DEVICE=cpu  # Change to 'cuda' for GPU pods
CORS_ORIGINS=https://ai-cost-optimizer-scientia-capital.vercel.app
TORCH_HOME=/app/model_cache
```

**Verify Deployment**:
```bash
curl https://YOUR_POD_ID-8000.proxy.runpod.net/health
# Expected: {"status": "healthy"}
```

## 8. Coding Standards

### FastAPI Specific Standards
```python
# Use Pydantic v2 style
from pydantic import BaseModel, Field

class PromptRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=10000)
    user_id: str | None = Field(None, description="Optional user identifier")

# Use async/await for I/O operations
@app.post("/chat")
async def chat_endpoint(request: PromptRequest):
    result = await router.route_prompt(request.prompt)
    return ChatResponse(**result.dict())
```

### Project-Specific Conventions
- Provider classes must implement `send_message()` method
- All cost calculations in USD cents for precision
- Use dependency injection for API clients
- Log all routing decisions and costs

### Error Handling Pattern
```python
try:
    response = await provider.send_message(prompt)
except ProviderError as e:
    logger.warning(f"Provider {provider.name} failed: {e}")
    return await fallback_provider.send_message(prompt)
```

## 9. Common Tasks & Commands

### Development Tasks
```bash
# Start development server
python app/main.py

# Run tests
pytest

# Check code style (if configured)
flake8 app/ tests/

# Format code (if configured)
black app/ tests/
```

### MCP Server Management
```bash
# Test MCP server directly
python mcp/server.py

# Update Claude Desktop config
# Edit: ~/Library/Application Support/Claude/claude_desktop_config.json
```

### Debugging Commands
```bash
# Check API health
curl http://localhost:8000/health

# Test routing directly
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Explain quantum computing"}'
```

## 10. Troubleshooting Tips

### Common Issues

**MCP Server Not Connecting**:
- Verify absolute path in Claude Desktop config
- Check `COST_OPTIMIZER_API_URL` environment variable
- Restart Claude Desktop completely (don't just relaunch)

**Provider API Errors**:
- Verify API keys in `.env` file
- Check provider service status
- Review API rate limits and quotas

**Database Issues**:
- Check Supabase credentials in `.env`
- Verify pgvector extension is enabled

### Debug Mode
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Or set in environment
LOG_LEVEL=DEBUG
```

### Health Check Endpoints
- `GET /health` - Service status
- `GET /providers` - Available provider status
- `GET /costs/summary` - Cost tracking summary

### Performance Monitoring
- Monitor response times in logs
- Track token usage patterns
- Review cost per provider in database

---

**Maintenance Note**: Regularly update provider API clients as LLM providers frequently change their interfaces and pricing structures.

**See Also**:
- `docs/COMMERCIALIZATION.md` for revenue models and go-to-market strategy
- `docs/REALTIME_SETUP.md` for real-time metrics integration guide