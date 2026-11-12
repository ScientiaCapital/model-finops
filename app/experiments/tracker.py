"""
ExperimentTracker - A/B Testing Framework

Manages A/B test experiments for routing strategy comparison:
- Deterministic user assignment (control vs test group)
- Result recording and aggregation
- Progress tracking toward sample size goals
- Statistical readiness detection
"""

import hashlib
import logging
import sqlite3
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


class ExperimentTracker:
    """
    Tracks A/B testing experiments for routing strategies.

    Provides deterministic user assignment and result aggregation
    to enable scientific comparison of routing strategies.
    """

    def __init__(self, db_path: str = "./costs.db") -> None:
        """
        Initialize ExperimentTracker with database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create experiment tables if they don't exist."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Create experiments table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS experiments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    control_strategy TEXT NOT NULL,
                    test_strategy TEXT NOT NULL,
                    sample_size INTEGER NOT NULL CHECK(sample_size > 0),
                    start_date TEXT NOT NULL,
                    end_date TEXT,
                    status TEXT NOT NULL
                        CHECK(status IN ('pending', 'active', 'completed', 'cancelled')),
                    created_at TEXT NOT NULL,
                    winner TEXT
                )
            """)

            # Create experiment_results table
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

            # Create indexes for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_experiments_status
                ON experiments(status, created_at)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_experiment_results_experiment_id
                ON experiment_results(experiment_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_experiment_results_strategy
                ON experiment_results(strategy_assigned)
            """)

            conn.commit()
        finally:
            conn.close()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with FK support enabled."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def create_experiment(
        self,
        name: str,
        control_strategy: str,
        test_strategy: str,
        sample_size: int,
        status: str = "active",
    ) -> int:
        """
        Create a new A/B test experiment.

        Args:
            name: Human-readable experiment name
            control_strategy: Baseline routing strategy
            test_strategy: Strategy being tested against control
            sample_size: Target number of results to collect
            status: Experiment status (default: 'active')

        Returns:
            experiment_id: Database ID of created experiment

        Raises:
            ValueError: If validation fails
        """
        # Input validation
        if not name or not name.strip():
            raise ValueError("Experiment name cannot be empty")

        if sample_size <= 0:
            raise ValueError(f"Sample size must be positive, got {sample_size}")

        if control_strategy == test_strategy:
            raise ValueError(
                f"Control and test strategies must be different, both set to '{control_strategy}'"
            )

        valid_strategies = {"complexity", "learning", "hybrid"}
        if control_strategy not in valid_strategies:
            raise ValueError(
                f"Invalid control strategy '{control_strategy}', must be one of {valid_strategies}"
            )

        if test_strategy not in valid_strategies:
            raise ValueError(
                f"Invalid test strategy '{test_strategy}', must be one of {valid_strategies}"
            )

        valid_statuses = {"active", "completed", "cancelled", "pending"}
        if status not in valid_statuses:
            raise ValueError(f"Invalid status '{status}', must be one of {valid_statuses}")

        logger.info(f"Creating experiment: {name} ({control_strategy} vs {test_strategy})")

        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO experiments
                (name, control_strategy, test_strategy, sample_size, start_date, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    name,
                    control_strategy,
                    test_strategy,
                    sample_size,
                    datetime.now(UTC).isoformat(),
                    status,
                    datetime.now(UTC).isoformat(),
                ),
            )

            conn.commit()
            experiment_id = cursor.lastrowid
            logger.info(f"Created experiment {experiment_id}")
            return experiment_id
        finally:
            conn.close()

    def get_active_experiments(self) -> list[dict[str, Any]]:
        """
        Retrieve all active experiments.

        Returns:
            List of experiment dicts with id, name, strategies, sample_size
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, name, control_strategy, test_strategy, sample_size, start_date
                FROM experiments
                WHERE status = 'active'
                ORDER BY created_at ASC
            """)

            experiments = []
            for row in cursor.fetchall():
                experiments.append(
                    {
                        "id": row[0],
                        "name": row[1],
                        "control_strategy": row[2],
                        "test_strategy": row[3],
                        "sample_size": row[4],
                        "start_date": row[5],
                    }
                )

            return experiments
        finally:
            conn.close()

    def complete_experiment(self, experiment_id: int, winner: str | None = None) -> None:
        """
        Mark experiment as completed.

        Args:
            experiment_id: ID of experiment to complete
            winner: Optional winning strategy name
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE experiments
                SET status = 'completed',
                    end_date = ?,
                    winner = ?
                WHERE id = ?
            """,
                (datetime.now(UTC).isoformat(), winner, experiment_id),
            )

            conn.commit()
            logger.info(f"Completed experiment {experiment_id} with winner: {winner}")
        finally:
            conn.close()

    def assign_user(self, experiment_id: int, user_id: str) -> str:
        """
        Assign user to control or test group using deterministic hashing.

        Same user_id will always get same assignment for given experiment.
        Uses SHA256(experiment_id + user_id) % 2 for 50/50 distribution.

        Args:
            experiment_id: ID of experiment
            user_id: User identifier

        Returns:
            strategy: Either control_strategy or test_strategy

        Raises:
            ValueError: If experiment not found
        """
        # Get experiment strategies
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT control_strategy, test_strategy
                FROM experiments
                WHERE id = ?
            """,
                (experiment_id,),
            )

            result = cursor.fetchone()

            if not result:
                raise ValueError(f"Experiment {experiment_id} not found")

            control_strategy, test_strategy = result
        finally:
            conn.close()

        # Deterministic hash-based assignment
        hash_input = f"{experiment_id}:{user_id}".encode()
        hash_digest = hashlib.sha256(hash_input).hexdigest()
        assignment = int(hash_digest, 16) % 2

        return control_strategy if assignment == 0 else test_strategy

    def record_result(
        self,
        experiment_id: int,
        user_id: str,
        strategy_assigned: str,
        latency_ms: float,
        cost_usd: float,
        quality_score: int | None,
        provider: str,
        model: str,
    ) -> int:
        """
        Record an experiment result (routing decision outcome).

        Args:
            experiment_id: ID of experiment
            user_id: User identifier
            strategy_assigned: Which strategy was used (control or test)
            latency_ms: Response latency in milliseconds
            cost_usd: API cost in USD
            quality_score: Optional quality rating (1-10)
            provider: AI provider used
            model: Model name used

        Returns:
            result_id: Database ID of recorded result
        """
        logger.debug(f"Recording result for experiment {experiment_id}, user {user_id}")

        conn = self._get_connection()
        try:
            cursor = conn.cursor()

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
                    strategy_assigned,
                    datetime.now(UTC).isoformat(),
                    latency_ms,
                    cost_usd,
                    quality_score,
                    provider,
                    model,
                ),
            )

            conn.commit()
            result_id = cursor.lastrowid
            return result_id
        finally:
            conn.close()

    def get_experiment_progress(self, experiment_id: int) -> dict[str, Any]:
        """
        Get progress toward sample_size goal.

        Args:
            experiment_id: ID of experiment

        Returns:
            Dict with experiment_id, sample_size, total_results, completion_percentage, is_complete
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Get sample_size
            cursor.execute("SELECT sample_size FROM experiments WHERE id = ?", (experiment_id,))
            result = cursor.fetchone()
            sample_size = result[0] if result else 0

            # Count total results
            cursor.execute(
                "SELECT COUNT(*) FROM experiment_results WHERE experiment_id = ?", (experiment_id,)
            )
            total_results = cursor.fetchone()[0]

            completion_percentage = (total_results / sample_size * 100) if sample_size > 0 else 0
            is_complete = total_results >= sample_size

            return {
                "experiment_id": experiment_id,
                "sample_size": sample_size,
                "total_results": total_results,
                "completion_percentage": completion_percentage,
                "is_complete": is_complete,
            }
        finally:
            conn.close()

    def get_experiment_summary(self, experiment_id: int) -> dict[str, dict[str, Any]]:
        """
        Get aggregated statistics by strategy (control vs test).

        Args:
            experiment_id: ID of experiment

        Returns:
            Dict with 'control' and 'test' keys, each containing:
            - strategy: strategy name
            - count: number of results
            - avg_latency_ms: average latency
            - avg_cost_usd: average cost
            - avg_quality_score: average quality
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Get experiment strategies
            cursor.execute(
                """
                SELECT control_strategy, test_strategy
                FROM experiments
                WHERE id = ?
            """,
                (experiment_id,),
            )

            exp_result = cursor.fetchone()
            if not exp_result:
                return {"control": {}, "test": {}}

            control_strategy, test_strategy = exp_result

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

            # Build summary dict
            summary = {
                "control": {
                    "strategy": control_strategy,
                    "count": 0,
                    "avg_latency_ms": 0.0,
                    "avg_cost_usd": 0.0,
                    "avg_quality_score": 0.0,
                },
                "test": {
                    "strategy": test_strategy,
                    "count": 0,
                    "avg_latency_ms": 0.0,
                    "avg_cost_usd": 0.0,
                    "avg_quality_score": 0.0,
                },
            }

            for row in results:
                strategy_assigned, count, avg_latency, avg_cost, avg_quality = row

                if strategy_assigned == control_strategy:
                    summary["control"].update(
                        {
                            "count": count,
                            "avg_latency_ms": avg_latency or 0.0,
                            "avg_cost_usd": avg_cost or 0.0,
                            "avg_quality_score": avg_quality or 0.0,
                        }
                    )
                elif strategy_assigned == test_strategy:
                    summary["test"].update(
                        {
                            "count": count,
                            "avg_latency_ms": avg_latency or 0.0,
                            "avg_cost_usd": avg_cost or 0.0,
                            "avg_quality_score": avg_quality or 0.0,
                        }
                    )

            return summary
        finally:
            conn.close()
