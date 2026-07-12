# AI Cost Optimizer - Technical Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Interfaces                          │
├──────────────────────┬──────────────────────┬───────────────────┤
│  Claude Desktop      │   REST API Client    │   Future: Web UI  │
│  (via MCP)           │   (curl, Python)     │   (Streamlit)     │
└──────────┬───────────┴──────────┬───────────┴───────────────────┘
           │                      │
           │ MCP Protocol         │ HTTP/REST
           │ (stdio)              │
           ▼                      ▼
┌────────────────────┐  ┌─────────────────────────────────────────┐
│   MCP Server       │  │      FastAPI Application                │
│   mcp/server.py    │  │      (main.py)                          │
│                    │  │                                          │
│  • 5 Tools         │  │  ┌────────────────────────────────────┐ │
│  • Protocol Bridge │  │  │        API Endpoints               │ │
│  • Error Handling  │──┼─▶│  POST /v1/complete                 │ │
│                    │  │  │  GET  /v1/models                   │ │
└────────────────────┘  │  │  GET  /v1/providers                │ │
                        │  │  GET  /v1/usage                    │ │
                        │  │  POST /v1/budget                   │ │
                        │  │  GET  /health                      │ │
                        │  │  GET  /metrics                     │ │
                        │  └────────────┬───────────────────────┘ │
                        │               │                          │
                        │               ▼                          │
                        │  ┌────────────────────────────────────┐ │
                        │  │      Core Components               │ │
                        │  ├────────────────────────────────────┤ │
                        │  │  • LLMRouter     (router.py)       │ │
                        │  │  • CostTracker   (cost_tracker.py) │ │
                        │  │  • BudgetManager (budget.py)       │ │
                        │  │  • ProviderMgr   (provider_mgr.py) │ │
                        │  └────────────┬───────────────────────┘ │
                        └───────────────┼─────────────────────────┘
                                       │
                                       ▼
                        ┌──────────────────────────────────────────┐
                        │      Provider Abstraction Layer          │
                        │      (providers/__init__.py)             │
                        └───────────┬──────────────────────────────┘
                                   │
                ┌──────────────────┼──────────────────┐
                │                  │                  │
                ▼                  ▼                  ▼
        ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
        │  Anthropic   │  │   Google     │  │  Cerebras    │
        │  Provider    │  │   Provider   │  │  Provider    │
        └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
               │                  │                  │
               ▼                  ▼                  ▼
        ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
        │ Claude API   │  │ Gemini API   │  │ Cerebras API │
        └──────────────┘  └──────────────┘  └──────────────┘

                        ┌──────────────────────────────────────────┐
                        │         Persistence Layer                 │
                        ├──────────────────────────────────────────┤
                        │  SQLite Database (optimizer.db)          │
                        │  • Cost history (planned)                │
                        │  • Budget tracking (planned)             │
                        │  • User preferences (future)             │
                        └──────────────────────────────────────────┘
```

See full architecture details in [ARCHITECTURE.md](./ARCHITECTURE.md) including:

- Detailed component descriptions
- Request flow diagrams
- Deployment architecture
- Performance characteristics
- Security considerations
- Future improvements

**TL;DR**: FastAPI backend routes prompts to 40+ models across 8 providers based on complexity analysis, tracks costs, enforces budgets, integrates with Claude Desktop via MCP protocol.
