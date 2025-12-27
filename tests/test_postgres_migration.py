"""Tests for PostgreSQL migration to feedback tables.

DEPRECATED: This test file is for the old PostgreSQL migration approach.
The project has migrated to Supabase. These tests are kept for reference only.
"""
import os
import pytest

# Skip this entire module - Supabase migration complete
pytest.skip(
    "PostgreSQL migration tests deprecated - using Supabase now",
    allow_module_level=True
)

TEST_DB_URL = os.getenv(
    'TEST_DATABASE_URL',
    'postgresql://test:test@localhost:5434/test_optimizer'
)


@pytest.fixture(scope="module")
def postgres_connection():
    """Create PostgreSQL connection for test database setup/teardown."""
    try:
        conn = psycopg2.connect(TEST_DB_URL)
        conn.autocommit = True
        yield conn
        conn.close()
    except psycopg2.OperationalError as e:
        pytest.skip(f"PostgreSQL not available: {e}")


@pytest.fixture(scope="module", autouse=True)
def setup_test_db(postgres_connection):
    """Set up and tear down test database."""
    cursor = postgres_connection.cursor()

    # Drop all tables to start fresh
    cursor.execute("""
        DROP SCHEMA public CASCADE;
        CREATE SCHEMA public;
        GRANT ALL ON SCHEMA public TO public;
    """)

    yield

    # Cleanup after all tests
    cursor.execute("""
        DROP SCHEMA public CASCADE;
        CREATE SCHEMA public;
        GRANT ALL ON SCHEMA public TO public;
    """)
    cursor.close()


@pytest.fixture
def alembic_config():
    """Create Alembic config for testing."""
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", TEST_DB_URL)
    return config


def test_feedback_tables_migration(alembic_config):
    """Test migration creates response_feedback table."""
    # Run migration
    command.upgrade(alembic_config, "head")

    # Connect and verify table exists
    conn = psycopg2.connect(TEST_DB_URL)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'response_feedback'
        ORDER BY ordinal_position
    """)

    columns = cursor.fetchall()
    column_names = [col[0] for col in columns]

    # Verify response_feedback table structure (from initial migration)
    assert 'id' in column_names
    assert 'cache_key' in column_names
    assert 'rating' in column_names
    assert 'comment' in column_names
    assert 'timestamp' in column_names

    cursor.close()
    conn.close()


def test_model_performance_history_migration(alembic_config):
    """Test migration creates model_performance_history table."""
    command.upgrade(alembic_config, "head")

    conn = psycopg2.connect(TEST_DB_URL)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'model_performance_history'
    """)

    columns = [row[0] for row in cursor.fetchall()]

    assert 'pattern' in columns
    assert 'provider' in columns
    assert 'model' in columns
    assert 'avg_quality_score' in columns
    assert 'correctness_rate' in columns
    assert 'sample_count' in columns
    assert 'confidence_level' in columns

    cursor.close()
    conn.close()


def test_foreign_key_constraint_exists(alembic_config):
    """Test foreign key constraint on response_feedback.request_id."""
    command.upgrade(alembic_config, "head")
    conn = psycopg2.connect(TEST_DB_URL)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'response_feedback'
        AND constraint_type = 'FOREIGN KEY'
    """)

    constraints = cursor.fetchall()
    assert len(constraints) > 0, "Foreign key constraint missing"

    cursor.close()
    conn.close()
