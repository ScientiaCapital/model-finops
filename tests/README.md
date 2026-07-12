# Test Suite

This directory contains the test suite for the AI Cost Optimizer.

## Test Categories

### 1. Integration Tests (SQLite)

Tests that verify end-to-end functionality using SQLite database.

**Run:**

```bash
pytest tests/test_integration_feedback_loop.py -v
```

**Features:**

- Mocked API calls (no real API keys needed)
- SQLite database for fast execution
- Tests feedback loop, retraining, and routing

### 2. PostgreSQL Migration Tests

Tests that verify database migrations work correctly with PostgreSQL.

**Prerequisites:**

```bash
# Start test PostgreSQL database
docker-compose -f docker-compose.test.yml up -d

# Wait for database to be healthy (about 5 seconds)
sleep 5
```

**Run:**

```bash
TEST_DATABASE_URL=postgresql://test:test@localhost:5434/test_optimizer pytest tests/test_postgres_migration.py -v
```

**Features:**

- Tests Alembic migrations on PostgreSQL
- Verifies table structures and constraints
- Automatically skipped if TEST_DATABASE_URL not set

**Cleanup:**

```bash
docker-compose -f docker-compose.test.yml down
```

## Running All Tests

To run all tests in the project:

```bash
# Unit tests (SQLite-based)
pytest tests/test_integration_feedback_loop.py -v

# PostgreSQL tests (requires docker)
docker-compose -f docker-compose.test.yml up -d
sleep 5
TEST_DATABASE_URL=postgresql://test:test@localhost:5434/test_optimizer pytest tests/test_postgres_migration.py -v
docker-compose -f docker-compose.test.yml down
```

## Test Configuration

### conftest.py

- Sets up SQLite database for integration tests
- Skips SQLite setup if `TEST_DATABASE_URL` is set (for PostgreSQL tests)
- Provides test client fixture for FastAPI

### Mocking

Integration tests mock all provider API calls to avoid:

- Authentication errors
- Rate limiting
- API costs
- External dependencies

## Continuous Integration

For CI environments, run:

```bash
# SQLite tests (always run)
pytest tests/test_integration_feedback_loop.py -v

# PostgreSQL tests (only if PostgreSQL is available)
if [ -n "$TEST_DATABASE_URL" ]; then
  pytest tests/test_postgres_migration.py -v
fi
```
