"""
Tests for A/B testing experiment schema and migrations.

This test suite validates the experiment tracking database schema:
- experiments table for defining A/B tests
- experiment_results table for recording routing decisions
- Foreign key relationships and constraints
- PostgreSQL and SQLite compatibility
"""

import os
import sqlite3
from datetime import UTC, datetime

import pytest


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="PostgreSQL tests require TEST_DATABASE_URL environment variable",
)
class TestExperimentSchemaPostgreSQL:
    """Test experiment schema with PostgreSQL (production database)."""

    def test_experiments_table_exists(self):
        """Verify experiments table is created with correct schema."""
        import psycopg2

        conn = psycopg2.connect(os.getenv("TEST_DATABASE_URL"))
        cursor = conn.cursor()

        # Check table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'experiments'
            )
        """)
        assert cursor.fetchone()[0] is True, "experiments table should exist"

        # Check columns
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'experiments'
            ORDER BY ordinal_position
        """)

        columns = cursor.fetchall()
        column_names = [col[0] for col in columns]

        expected_columns = [
            "id",
            "name",
            "control_strategy",
            "test_strategy",
            "sample_size",
            "start_date",
            "end_date",
            "status",
            "created_at",
            "winner",
        ]

        for expected_col in expected_columns:
            assert expected_col in column_names, f"Column {expected_col} should exist"

        conn.close()

    def test_experiment_results_table_exists(self):
        """Verify experiment_results table is created with correct schema."""
        import psycopg2

        conn = psycopg2.connect(os.getenv("TEST_DATABASE_URL"))
        cursor = conn.cursor()

        # Check table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'experiment_results'
            )
        """)
        assert cursor.fetchone()[0] is True, "experiment_results table should exist"

        # Check columns
        cursor.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'experiment_results'
            ORDER BY ordinal_position
        """)

        columns = cursor.fetchall()
        column_names = [col[0] for col in columns]

        expected_columns = [
            "id",
            "experiment_id",
            "user_id",
            "strategy_assigned",
            "timestamp",
            "latency_ms",
            "cost_usd",
            "quality_score",
            "provider",
            "model",
        ]

        for expected_col in expected_columns:
            assert expected_col in column_names, f"Column {expected_col} should exist"

        conn.close()

    def test_foreign_key_constraint_exists(self):
        """Verify foreign key from experiment_results to experiments."""
        import psycopg2

        conn = psycopg2.connect(os.getenv("TEST_DATABASE_URL"))
        cursor = conn.cursor()

        cursor.execute("""
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_name = 'experiment_results'
            AND constraint_type = 'FOREIGN KEY'
        """)

        fk_constraints = cursor.fetchall()
        assert len(fk_constraints) > 0, "Should have at least one foreign key constraint"

        conn.close()


class TestExperimentSchemaSQLite:
    """Test experiment schema with SQLite (test database)."""

    def test_experiments_table_created(self, client):
        """Verify experiments table exists in SQLite test database."""
        db_path = "./test_feedback.db"
        assert os.path.exists(db_path), "Test database should exist"

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='experiments'
        """)
        result = cursor.fetchone()
        assert result is not None, "experiments table should exist"

        # Check schema
        cursor.execute("PRAGMA table_info(experiments)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        expected_columns = [
            "id",
            "name",
            "control_strategy",
            "test_strategy",
            "sample_size",
            "start_date",
            "end_date",
            "status",
            "created_at",
            "winner",
        ]

        for expected_col in expected_columns:
            assert expected_col in column_names, f"Column {expected_col} should exist"

        conn.close()

    def test_experiment_results_table_created(self, client):
        """Verify experiment_results table exists in SQLite test database."""
        db_path = "./test_feedback.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='experiment_results'
        """)
        result = cursor.fetchone()
        assert result is not None, "experiment_results table should exist"

        # Check schema
        cursor.execute("PRAGMA table_info(experiment_results)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        expected_columns = [
            "id",
            "experiment_id",
            "user_id",
            "strategy_assigned",
            "timestamp",
            "latency_ms",
            "cost_usd",
            "quality_score",
            "provider",
            "model",
        ]

        for expected_col in expected_columns:
            assert expected_col in column_names, f"Column {expected_col} should exist"

        conn.close()

    def test_experiment_crud_operations(self, client):
        """Test basic CRUD operations on experiments table."""
        db_path = "./test_feedback.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create experiment
        cursor.execute(
            """
            INSERT INTO experiments
            (name, control_strategy, test_strategy, sample_size, start_date, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                "Test Experiment",
                "complexity",
                "learning",
                100,
                datetime.now(UTC).isoformat(),
                "active",
                datetime.now(UTC).isoformat(),
            ),
        )
        conn.commit()

        experiment_id = cursor.lastrowid
        assert experiment_id > 0, "Should return valid experiment ID"

        # Read experiment
        cursor.execute("SELECT name, status FROM experiments WHERE id = ?", (experiment_id,))
        result = cursor.fetchone()
        assert result[0] == "Test Experiment"
        assert result[1] == "active"

        # Update experiment
        cursor.execute(
            """
            UPDATE experiments SET status = ? WHERE id = ?
        """,
            ("completed", experiment_id),
        )
        conn.commit()

        cursor.execute("SELECT status FROM experiments WHERE id = ?", (experiment_id,))
        assert cursor.fetchone()[0] == "completed"

        # Delete experiment
        cursor.execute("DELETE FROM experiments WHERE id = ?", (experiment_id,))
        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM experiments WHERE id = ?", (experiment_id,))
        assert cursor.fetchone()[0] == 0

        conn.close()

    def test_experiment_results_crud_operations(self, client):
        """Test recording experiment results."""
        db_path = "./test_feedback.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create experiment first
        cursor.execute(
            """
            INSERT INTO experiments
            (name, control_strategy, test_strategy, sample_size, start_date, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                "Results Test",
                "complexity",
                "hybrid",
                50,
                datetime.now(UTC).isoformat(),
                "active",
                datetime.now(UTC).isoformat(),
            ),
        )
        conn.commit()
        experiment_id = cursor.lastrowid

        # Insert result
        cursor.execute(
            """
            INSERT INTO experiment_results
            (experiment_id, user_id, strategy_assigned, timestamp, latency_ms, cost_usd,
             quality_score, provider, model)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                experiment_id,
                "user123",
                "complexity",
                datetime.now(UTC).isoformat(),
                45.5,
                0.0012,
                8,
                "gemini",
                "gemini-1.5-flash",
            ),
        )
        conn.commit()

        result_id = cursor.lastrowid
        assert result_id > 0

        # Query result
        cursor.execute(
            """
            SELECT user_id, strategy_assigned, latency_ms, cost_usd
            FROM experiment_results
            WHERE id = ?
        """,
            (result_id,),
        )

        result = cursor.fetchone()
        assert result[0] == "user123"
        assert result[1] == "complexity"
        assert result[2] == 45.5
        assert result[3] == 0.0012

        # Cleanup
        cursor.execute("DELETE FROM experiment_results WHERE experiment_id = ?", (experiment_id,))
        cursor.execute("DELETE FROM experiments WHERE id = ?", (experiment_id,))
        conn.commit()
        conn.close()

    def test_foreign_key_constraint_enforced(self, client):
        """Verify foreign key constraint prevents orphaned results."""
        db_path = "./test_feedback.db"
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")  # Enable FK constraints
        cursor = conn.cursor()

        # Try to insert result with non-existent experiment_id
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                """
                INSERT INTO experiment_results
                (experiment_id, user_id, strategy_assigned, timestamp, latency_ms, cost_usd,
             quality_score, provider, model)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    99999,  # Non-existent experiment
                    "user456",
                    "learning",
                    datetime.now(UTC).isoformat(),
                    50.0,
                    0.002,
                    7,
                    "claude",
                    "claude-3-haiku",
                ),
            )
            conn.commit()

        conn.close()

    def test_experiment_status_enum_values(self, client):
        """Test that experiment status accepts valid values."""
        db_path = "./test_feedback.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        valid_statuses = ["active", "completed", "cancelled", "pending"]

        for status in valid_statuses:
            cursor.execute(
                """
                INSERT INTO experiments
                (name, control_strategy, test_strategy, sample_size, start_date, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    f"Test {status}",
                    "complexity",
                    "learning",
                    100,
                    datetime.now(UTC).isoformat(),
                    status,
                    datetime.now(UTC).isoformat(),
                ),
            )
            conn.commit()

            cursor.execute("SELECT status FROM experiments WHERE name = ?", (f"Test {status}",))
            assert cursor.fetchone()[0] == status

        # Cleanup
        cursor.execute("DELETE FROM experiments WHERE name LIKE 'Test %'")
        conn.commit()
        conn.close()

    def test_experiment_aggregation_query(self, client):
        """Test aggregating results by strategy for an experiment."""
        db_path = "./test_feedback.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create experiment
        cursor.execute(
            """
            INSERT INTO experiments
            (name, control_strategy, test_strategy, sample_size, start_date, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                "Aggregation Test",
                "complexity",
                "learning",
                10,
                datetime.now(UTC).isoformat(),
                "active",
                datetime.now(UTC).isoformat(),
            ),
        )
        conn.commit()
        experiment_id = cursor.lastrowid

        # Insert multiple results for both strategies
        test_data = [
            ("user1", "complexity", 40.0, 0.001, 8),
            ("user2", "complexity", 45.0, 0.0012, 7),
            ("user3", "learning", 35.0, 0.0015, 9),
            ("user4", "learning", 38.0, 0.0014, 9),
        ]

        for user_id, strategy, latency, cost, quality in test_data:
            cursor.execute(
                """
                INSERT INTO experiment_results
                (experiment_id, user_id, strategy_assigned, timestamp, latency_ms, cost_usd,
             quality_score, provider, model)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    experiment_id,
                    user_id,
                    strategy,
                    datetime.now(UTC).isoformat(),
                    latency,
                    cost,
                    quality,
                    "gemini",
                    "gemini-1.5-flash",
                ),
            )
        conn.commit()

        # Aggregate by strategy
        cursor.execute(
            """
            SELECT
                strategy_assigned,
                COUNT(*) as count,
                AVG(latency_ms) as avg_latency,
                AVG(cost_usd) as avg_cost,
                AVG(quality_score) as avg_quality
            FROM experiment_results
            WHERE experiment_id = ?
            GROUP BY strategy_assigned
        """,
            (experiment_id,),
        )

        results = cursor.fetchall()
        assert len(results) == 2, "Should have results for both strategies"

        # Verify aggregations
        for row in results:
            strategy, count, avg_latency, avg_cost, avg_quality = row
            assert count == 2, "Each strategy should have 2 results"

            if strategy == "complexity":
                assert 42.0 <= avg_latency <= 43.0, "Average latency should be ~42.5"
                assert avg_quality >= 7.0
            elif strategy == "learning":
                assert 36.0 <= avg_latency <= 37.0, "Average latency should be ~36.5"
                assert avg_quality >= 9.0

        # Cleanup
        cursor.execute("DELETE FROM experiment_results WHERE experiment_id = ?", (experiment_id,))
        cursor.execute("DELETE FROM experiments WHERE id = ?", (experiment_id,))
        conn.commit()
        conn.close()
