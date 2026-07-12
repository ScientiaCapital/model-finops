# Development Guide

This guide helps you set up and contribute to the AI Cost Optimizer project.

## Quick Start

1. **Clone and setup:**

   ```bash
   git clone <repo-url>
   cd ai-cost-optimizer
   make setup
   ```

2. **Configure environment:**

   ```bash
   cp .env.example .env
   # Edit .env and add your API keys
   ```

3. **Run development servers:**
   ```bash
   make dev  # Runs both backend and frontend
   ```

## Project Structure

```
ai-cost-optimizer/
├── app/                  # Python FastAPI backend
│   ├── main.py          # FastAPI app and routes
│   ├── providers.py     # LLM provider implementations
│   ├── router.py        # Smart routing logic
│   ├── complexity.py    # Complexity analysis
│   └── database.py      # SQLite cost tracking
├── next-app/            # Next.js frontend
│   ├── app/             # Next.js app router
│   ├── components/     # React components
│   └── lib/             # Shared utilities
├── mcp/                 # MCP server for Claude Desktop
├── scripts/             # Utility scripts
└── tests/               # Test files (create if needed)
```

## Development Workflow

### Running the Application

```bash
# Run both backend and frontend
make dev

# Or run separately:
make backend   # FastAPI on http://localhost:8000
make frontend  # Next.js on http://localhost:3000
```

### Code Quality

```bash
# Format code
make format

# Lint code
make lint

# Type check
make typecheck
```

### Testing

```bash
# Run all tests
make test

# Run Python tests only
pytest tests/

# Run TypeScript tests only
cd next-app && npm test
```

## Code Style

### Python

- Follow PEP 8 style guide
- Use `black` for formatting (configured in `pyproject.toml`)
- Use `isort` for import sorting
- Maximum line length: 100 characters
- Type hints encouraged (mypy configured)

**Format before committing:**

```bash
make format
```

### TypeScript/React

- Use TypeScript strict mode
- Follow Next.js conventions
- Use Prettier for formatting (configured in `.prettierrc`)
- Maximum line length: 100 characters
- Use functional components with hooks

**Format before committing:**

```bash
cd next-app && npm run format
```

## Environment Variables

See `.env.example` for all available configuration options.

**Required for development:**

- At least one provider API key (GOOGLE_API_KEY, ANTHROPIC_API_KEY, etc.)

**Optional:**

- `CORS_ORIGINS` - Comma-separated origins (default: "*")
- `PORT` - Backend port (default: 8000)
- `LOG_LEVEL` - Logging verbosity (default: INFO)

## Database

The SQLite database (`optimizer.db`) is created automatically on first run.

**Reset database:**

```bash
make db-reset
```

**Note:** This deletes all tracked costs and cache data!

## Adding a New Provider

1. Create provider class in `app/providers.py`:

   ```python
   class NewProvider(Provider):
       async def complete(self, prompt, max_tokens):
           # Implementation
   ```

2. Add to `init_providers()` in `app/providers.py`

3. Update routing logic in `app/router.py` if needed

4. Add API key to `.env.example`

## Debugging

### Backend (FastAPI)

- Logs appear in console
- Check `http://localhost:8000/docs` for interactive API docs
- Use `ipdb` for debugging (installed in dev dependencies)

### Frontend (Next.js)

- Browser DevTools for React debugging
- Next.js error overlay shows compilation errors
- Check terminal for server-side errors

### MCP Server

- Check Claude Desktop logs for MCP errors
- Test MCP server directly:
  ```bash
  python mcp/server.py
  ```

## Git Workflow

1. Create a branch for your feature:

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make changes and test:

   ```bash
   make lint format test
   ```

3. Commit with clear messages:

   ```bash
   git commit -m "feat: add new provider"
   ```

4. Push and create PR

## Common Tasks

### Update Dependencies

```bash
# Python
pip install -r requirements-dev.txt --upgrade

# Node.js
cd next-app && npm update
```

### Clean Build Artifacts

```bash
make clean  # Removes caches
make clean-all  # Removes node_modules and venv
```

### Check Code Quality Before PR

```bash
make lint format typecheck test
```

## Troubleshooting

### Backend won't start

- Check API keys are set in `.env`
- Verify Python version >= 3.10: `python --version`
- Check port 8000 is available: `lsof -i :8000`

### Frontend build errors

- Clear Next.js cache: `cd next-app && rm -rf .next`
- Reinstall dependencies: `cd next-app && rm -rf node_modules && npm install`

### Import errors

- Make sure virtual environment is activated
- Install dependencies: `pip install -r requirements-dev.txt`
- For Python: Use `python -m app.main` instead of `python app/main.py`

### Database locked errors

- Close any database connections
- Delete and recreate: `make db-reset`

## Resources

- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Next.js Docs](https://nextjs.org/docs)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)

## Getting Help

- Check existing issues on GitHub
- Review `TECH_AUDIT.md` for known issues
- Ask in team chat or create an issue
