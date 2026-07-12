# Coding Rules — model-finops

## LLM / AI

- Never use OpenAI SDK, GPT models, or `openai` package
- Providers: Anthropic Claude, Google Gemini, Cerebras, OpenRouter (non-OpenAI models)
- All provider classes must implement `send_message()` method

## Python (Backend)

- All I/O operations must be `async/await` — no blocking calls in FastAPI handlers
- All cost calculations in USD cents (integer) for precision — never floats
- Routing strategies live in `app/routing/` only — no inline routing logic elsewhere
- Use dependency injection for API clients (FastAPI `Depends`)

## Database

- Semantic cache threshold is 0.95 — never lower it without testing cache hit quality
- All user data access must go through RLS (use anon key, not service key, for user-facing calls)
- Embeddings are 384D (all-MiniLM-L6-v2) — do not mix with other dimensions

## Testing

- `pytest tests/` must pass before any provider or routing change
- Mock provider responses — never make real API calls in tests
