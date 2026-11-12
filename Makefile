.PHONY: help install test lint format requirements backend frontend clean

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Install locked dependencies (plus the dev group) into .venv
	uv sync --frozen

test: ## Run the offline test suite
	uv run --frozen python -m pytest -q

lint: ## ruff check and format check, as CI runs them
	uv run --frozen ruff check app tests
	uv run --frozen ruff format --check app tests

format: ## Apply ruff fixes and formatting
	uv run --frozen ruff check --fix app tests
	uv run --frozen ruff format app tests

requirements: ## Regenerate requirements.txt and requirements-embeddings.txt (used by the Dockerfile) from uv.lock
	uv export --frozen --no-hashes --no-dev --no-emit-project -o requirements.txt
	uv export --frozen --no-hashes --no-dev --no-emit-project --extra embeddings -o requirements-embeddings.txt

backend: ## Run the FastAPI service with reload on http://127.0.0.1:8000
	uv run --frozen uvicorn app.main:app --reload

frontend: ## Run the Next.js frontend
	cd frontend && npm run dev

clean: ## Remove caches
	find . -type d -name "__pycache__" -not -path "./.venv*" -exec rm -r {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache

.DEFAULT_GOAL := help
