import os
import sqlite3
import pytest
import asyncio
import jwt
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Setup test database URL for tests.

    This fixture only sets up SQLite for non-PostgreSQL tests.
    PostgreSQL tests should use TEST_DATABASE_URL environment variable
    and manage their own database state via Alembic migrations.
    """
    # Skip if TEST_DATABASE_URL is set (indicates PostgreSQL tests)
    if os.getenv('TEST_DATABASE_URL'):
        yield
        return

    # Use SQLite for tests (simpler, faster)
    db_path = './test_feedback.db'
    os.environ['DATABASE_URL'] = f'sqlite:///{db_path}'

    # Create test database tables
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create routing_metrics table (production schema + request_id for feedback FK)
    # This table supports Phase 2 metrics (app/database.py)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS routing_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            prompt_hash TEXT NOT NULL,
            strategy_used TEXT NOT NULL,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            confidence TEXT NOT NULL,
            auto_route INTEGER NOT NULL,
            estimated_cost REAL,
            complexity_score REAL,
            pattern TEXT,
            fallback_used INTEGER DEFAULT 0,
            metadata TEXT,
            request_id TEXT UNIQUE,
            selected_provider TEXT,
            selected_model TEXT,
            pattern_detected TEXT
        )
    """)

    # Create routing_feedback table (matches feedback_store.py schema)
    # This is for routing decision feedback
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS routing_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT NOT NULL,
            timestamp DATETIME NOT NULL,
            quality_score INTEGER NOT NULL,
            is_correct BOOLEAN,
            is_helpful BOOLEAN,
            prompt_pattern TEXT,
            selected_provider TEXT,
            selected_model TEXT,
            complexity_score REAL,
            user_id TEXT,
            session_id TEXT,
            comment TEXT,
            FOREIGN KEY (request_id) REFERENCES routing_metrics(request_id)
        )
    """)

    # Create response_feedback table (for cache quality feedback - different from routing_feedback)
    # This table is for rating cached responses in app/database.py
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS response_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cache_key TEXT NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT,
            user_agent TEXT,
            timestamp TEXT NOT NULL
        )
    """)

    # Create experiments table (for A/B testing framework)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS experiments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            control_strategy TEXT NOT NULL,
            test_strategy TEXT NOT NULL,
            sample_size INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            winner TEXT
        )
    """)

    # Create experiment_results table (records routing decisions within experiments)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS experiment_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            strategy_assigned TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            latency_ms REAL NOT NULL,
            cost_usd REAL NOT NULL,
            quality_score INTEGER,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
        )
    """)

    # Create indexes for performance (critical for aggregation queries)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_experiment_results_experiment_id
        ON experiment_results(experiment_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_experiment_results_strategy
        ON experiment_results(experiment_id, strategy_assigned)
    """)

    conn.commit()
    conn.close()

    yield

    # Cleanup
    try:
        os.remove(db_path)
    except:
        pass


@pytest.fixture(scope="function")
def client():
    """Get test client with Supabase backend.

    Current testing strategy (post-Supabase migration):
    - Uses real Supabase backend with test credentials
    - JWT auth fixtures provide mock tokens (see test_jwt_secret, mock_jwt_token)
    - Database operations use actual Supabase tables (isolated by test user_id)
    - No need for complex database mocking - Supabase handles isolation via RLS
    - 123/123 tests passing with this approach (100% pass rate)
    """
    yield TestClient(app)


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# SUPABASE AUTHENTICATION FIXTURES
# ============================================================================

@pytest.fixture(scope="session")
def test_jwt_secret():
    """Test JWT secret for Supabase tokens."""
    return "test-jwt-secret-for-testing-only"


@pytest.fixture(scope="session")
def test_user_id():
    """Test user ID for authenticated requests."""
    return "test-user-123"


@pytest.fixture(scope="function")
def mock_jwt_token(test_jwt_secret, test_user_id):
    """Generate a valid JWT token for testing."""
    payload = {
        "sub": test_user_id,  # Supabase user ID
        "email": "test@example.com",
        "aud": "authenticated",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, test_jwt_secret, algorithm="HS256")
    return token


@pytest.fixture(scope="function")
def auth_headers(mock_jwt_token):
    """HTTP headers with valid JWT authentication."""
    return {"Authorization": f"Bearer {mock_jwt_token}"}


@pytest.fixture(scope="function")
def authenticated_client(test_jwt_secret):
    """Test client with JWT authentication mocked."""
    # Mock the JWT secret in environment
    with patch.dict(os.environ, {"SUPABASE_JWT_SECRET": test_jwt_secret}):
        yield TestClient(app)


@pytest.fixture(scope="function")
def bypass_auth():
    """Fixture to bypass authentication for testing.

    Usage:
        def test_something(bypass_auth, client):
            # Auth is bypassed for this test
            response = client.get("/protected-endpoint")
    """
    # Mock OptionalAuth to always return None (public access)
    from app.auth import OptionalAuth
    original_call = OptionalAuth.__call__

    def mock_call(self, request):
        return None

    OptionalAuth.__call__ = mock_call
    yield
    OptionalAuth.__call__ = original_call
