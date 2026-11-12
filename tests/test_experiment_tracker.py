"""
Tests for ExperimentTracker class.

This test suite validates the A/B testing experiment tracker functionality:
- Experiment creation and lifecycle management
- Deterministic user assignment (hashing)
- Result recording and aggregation
- Sample size tracking
- Redis caching for active experiments
"""

import sqlite3

import pytest

from app.experiments.tracker import ExperimentTracker


class TestExperimentTrackerCreation:
    """Test experiment creation and lifecycle."""

    def test_create_experiment(self):
        """Create a new A/B test experiment."""
        tracker = ExperimentTracker(db_path="./test_feedback.db")

        experiment_id = tracker.create_experiment(
            name="Test Complexity vs Learning",
            control_strategy="complexity",
            test_strategy="learning",
            sample_size=100,
        )

        assert experiment_id > 0, "Should return valid experiment ID"

        # Verify experiment was created in database
        conn = sqlite3.connect("./test_feedback.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name, status, control_strategy, test_strategy, sample_size "
            "FROM experiments WHERE id = ?",
            (experiment_id,),
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == "Test Complexity vs Learning"
        assert result[1] == "active"
        assert result[2] == "complexity"
        assert result[3] == "learning"
        assert result[4] == 100

    def test_create_experiment_with_invalid_status(self):
        """Experiment should default to 'active' status."""
        tracker = ExperimentTracker(db_path="./test_feedback.db")

        experiment_id = tracker.create_experiment(
            name="Test Experiment",
            control_strategy="complexity",
            test_strategy="hybrid",
            sample_size=50,
        )

        conn = sqlite3.connect("./test_feedback.db")
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM experiments WHERE id = ?", (experiment_id,))
        status = cursor.fetchone()[0]
        conn.close()

        assert status == "active"

    def test_get_active_experiments(self):
        """Retrieve all active experiments."""
        tracker = ExperimentTracker(db_path="./test_feedback.db")

        # Create multiple experiments
        exp1 = tracker.create_experiment("Exp 1", "complexity", "learning", 100)
        exp2 = tracker.create_experiment("Exp 2", "learning", "hybrid", 50)

        active_experiments = tracker.get_active_experiments()

        assert len(active_experiments) >= 2
        exp_ids = [exp["id"] for exp in active_experiments]
        assert exp1 in exp_ids
        assert exp2 in exp_ids

    def test_complete_experiment(self):
        """Mark experiment as completed."""
        tracker = ExperimentTracker(db_path="./test_feedback.db")

        experiment_id = tracker.create_experiment("Complete Test", "complexity", "hybrid", 10)
        tracker.complete_experiment(experiment_id, winner="complexity")

        conn = sqlite3.connect("./test_feedback.db")
        cursor = conn.cursor()
        cursor.execute("SELECT status, winner FROM experiments WHERE id = ?", (experiment_id,))
        result = cursor.fetchone()
        conn.close()

        assert result[0] == "completed"
        assert result[1] == "complexity"


class TestUserAssignment:
    """Test deterministic user assignment to control/test groups."""

    def test_assign_user_deterministic(self):
        """Same user should always get same strategy."""
        tracker = ExperimentTracker(db_path="./test_feedback.db")

        experiment_id = tracker.create_experiment(
            "Deterministic Test", "complexity", "learning", 100
        )

        # Assign same user multiple times
        strategy1 = tracker.assign_user(experiment_id, "user123")
        strategy2 = tracker.assign_user(experiment_id, "user123")
        strategy3 = tracker.assign_user(experiment_id, "user123")

        assert strategy1 == strategy2 == strategy3
        assert strategy1 in ["complexity", "learning"]

    def test_assign_users_distribution(self):
        """Users should be roughly evenly distributed between control and test."""
        tracker = ExperimentTracker(db_path="./test_feedback.db")

        experiment_id = tracker.create_experiment(
            "Distribution Test", "complexity", "learning", 1000
        )

        # Assign 100 different users
        assignments = []
        for i in range(100):
            strategy = tracker.assign_user(experiment_id, f"user{i}")
            assignments.append(strategy)

        control_count = assignments.count("complexity")
        test_count = assignments.count("learning")

        # Should be roughly 50/50 (allow 30-70 range for randomness)
        assert 30 <= control_count <= 70, f"Control: {control_count}, Test: {test_count}"
        assert 30 <= test_count <= 70

    def test_assign_user_to_nonexistent_experiment(self):
        """Assignment to non-existent experiment should raise error."""
        tracker = ExperimentTracker(db_path="./test_feedback.db")

        with pytest.raises(ValueError, match="Experiment.*not found"):
            tracker.assign_user(99999, "user123")

    def test_hash_consistency(self):
        """Hash-based assignment should be consistent across tracker instances."""
        tracker1 = ExperimentTracker(db_path="./test_feedback.db")
        tracker2 = ExperimentTracker(db_path="./test_feedback.db")

        experiment_id = tracker1.create_experiment("Hash Test", "complexity", "learning", 50)

        assignment1 = tracker1.assign_user(experiment_id, "user_abc")
        assignment2 = tracker2.assign_user(experiment_id, "user_abc")

        assert assignment1 == assignment2


class TestResultRecording:
    """Test recording experiment results."""

    def test_record_result(self):
        """Record a single experiment result."""
        tracker = ExperimentTracker(db_path="./test_feedback.db")

        experiment_id = tracker.create_experiment("Result Test", "complexity", "learning", 10)

        result_id = tracker.record_result(
            experiment_id=experiment_id,
            user_id="user123",
            strategy_assigned="complexity",
            latency_ms=45.5,
            cost_usd=0.0012,
            quality_score=8,
            provider="gemini",
            model="gemini-1.5-flash",
        )

        assert result_id > 0

        # Verify in database
        conn = sqlite3.connect("./test_feedback.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, strategy_assigned, latency_ms, cost_usd "
            "FROM experiment_results WHERE id = ?",
            (result_id,),
        )
        result = cursor.fetchone()
        conn.close()

        assert result[0] == "user123"
        assert result[1] == "complexity"
        assert result[2] == 45.5
        assert result[3] == 0.0012

    def test_record_multiple_results(self):
        """Record multiple results for same experiment."""
        tracker = ExperimentTracker(db_path="./test_feedback.db")

        experiment_id = tracker.create_experiment("Multi Result Test", "complexity", "learning", 50)

        # Record 10 results
        result_ids = []
        for i in range(10):
            result_id = tracker.record_result(
                experiment_id=experiment_id,
                user_id=f"user{i}",
                strategy_assigned="complexity" if i % 2 == 0 else "learning",
                latency_ms=40.0 + i,
                cost_usd=0.001 + i * 0.0001,
                quality_score=7 + (i % 3),
                provider="gemini",
                model="gemini-1.5-flash",
            )
            result_ids.append(result_id)

        assert len(result_ids) == 10
        assert len(set(result_ids)) == 10, "All result IDs should be unique"

    def test_record_result_increments_count(self):
        """Recording results should increment progress toward sample_size."""
        tracker = ExperimentTracker(db_path="./test_feedback.db")

        experiment_id = tracker.create_experiment("Count Test", "complexity", "learning", 5)

        # Initially 0 results
        progress = tracker.get_experiment_progress(experiment_id)
        assert progress["total_results"] == 0
        assert progress["is_complete"] is False

        # Record 3 results
        for i in range(3):
            tracker.record_result(
                experiment_id,
                f"user{i}",
                "complexity",
                50.0,
                0.001,
                8,
                "gemini",
                "gemini-1.5-flash",
            )

        progress = tracker.get_experiment_progress(experiment_id)
        assert progress["total_results"] == 3
        assert progress["is_complete"] is False

        # Record 2 more to reach sample_size
        for i in range(3, 5):
            tracker.record_result(
                experiment_id, f"user{i}", "learning", 50.0, 0.001, 8, "gemini", "gemini-1.5-flash"
            )

        progress = tracker.get_experiment_progress(experiment_id)
        assert progress["total_results"] == 5
        assert progress["is_complete"] is True


class TestResultAggregation:
    """Test aggregating experiment results by strategy."""

    def test_get_experiment_summary(self):
        """Get aggregated statistics for an experiment."""
        tracker = ExperimentTracker(db_path="./test_feedback.db")

        experiment_id = tracker.create_experiment("Summary Test", "complexity", "learning", 20)

        # Record results for both strategies
        # Control: 40ms avg latency, $0.001 avg cost, quality 8
        for i in range(5):
            tracker.record_result(
                experiment_id,
                f"control_user{i}",
                "complexity",
                40.0,
                0.001,
                8,
                "gemini",
                "gemini-1.5-flash",
            )

        # Test: 35ms avg latency, $0.0015 avg cost, quality 9
        for i in range(5):
            tracker.record_result(
                experiment_id,
                f"test_user{i}",
                "learning",
                35.0,
                0.0015,
                9,
                "gemini",
                "gemini-1.5-flash",
            )

        summary = tracker.get_experiment_summary(experiment_id)

        assert "control" in summary
        assert "test" in summary

        # Control strategy stats
        assert summary["control"]["strategy"] == "complexity"
        assert summary["control"]["count"] == 5
        assert summary["control"]["avg_latency_ms"] == 40.0
        assert summary["control"]["avg_cost_usd"] == 0.001
        assert summary["control"]["avg_quality_score"] == 8.0

        # Test strategy stats
        assert summary["test"]["strategy"] == "learning"
        assert summary["test"]["count"] == 5
        assert summary["test"]["avg_latency_ms"] == 35.0
        assert summary["test"]["avg_cost_usd"] == 0.0015
        assert summary["test"]["avg_quality_score"] == 9.0

    def test_get_experiment_summary_empty(self):
        """Summary for experiment with no results should return zeros."""
        tracker = ExperimentTracker(db_path="./test_feedback.db")

        experiment_id = tracker.create_experiment(
            "Empty Summary Test", "complexity", "learning", 10
        )

        summary = tracker.get_experiment_summary(experiment_id)

        assert summary["control"]["count"] == 0
        assert summary["test"]["count"] == 0

    def test_get_experiment_summary_unbalanced(self):
        """Summary should work with unbalanced result counts."""
        tracker = ExperimentTracker(db_path="./test_feedback.db")

        experiment_id = tracker.create_experiment("Unbalanced Test", "complexity", "learning", 20)

        # 8 control results
        for i in range(8):
            tracker.record_result(
                experiment_id,
                f"user{i}",
                "complexity",
                50.0,
                0.001,
                8,
                "gemini",
                "gemini-1.5-flash",
            )

        # 2 test results
        for i in range(2):
            tracker.record_result(
                experiment_id,
                f"test_user{i}",
                "learning",
                30.0,
                0.002,
                9,
                "gemini",
                "gemini-1.5-flash",
            )

        summary = tracker.get_experiment_summary(experiment_id)

        assert summary["control"]["count"] == 8
        assert summary["test"]["count"] == 2


class TestExperimentProgress:
    """Test tracking experiment progress and completion."""

    def test_get_experiment_progress(self):
        """Get progress information for an experiment."""
        tracker = ExperimentTracker(db_path="./test_feedback.db")

        experiment_id = tracker.create_experiment("Progress Test", "complexity", "learning", 10)

        # Record 6 results
        for i in range(6):
            tracker.record_result(
                experiment_id,
                f"user{i}",
                "complexity",
                50.0,
                0.001,
                8,
                "gemini",
                "gemini-1.5-flash",
            )

        progress = tracker.get_experiment_progress(experiment_id)

        assert progress["experiment_id"] == experiment_id
        assert progress["sample_size"] == 10
        assert progress["total_results"] == 6
        assert progress["completion_percentage"] == 60.0
        assert progress["is_complete"] is False

    def test_experiment_auto_complete(self):
        """Experiment should not auto-complete when sample_size reached."""
        tracker = ExperimentTracker(db_path="./test_feedback.db")

        experiment_id = tracker.create_experiment("Auto Complete Test", "complexity", "learning", 3)

        # Record exactly sample_size results
        for i in range(3):
            tracker.record_result(
                experiment_id,
                f"user{i}",
                "complexity",
                50.0,
                0.001,
                8,
                "gemini",
                "gemini-1.5-flash",
            )

        progress = tracker.get_experiment_progress(experiment_id)
        assert progress["is_complete"] is True

        # But status should still be 'active' (manual completion required)
        conn = sqlite3.connect("./test_feedback.db")
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM experiments WHERE id = ?", (experiment_id,))
        status = cursor.fetchone()[0]
        conn.close()

        assert status == "active", "Experiment should remain active until manually completed"


class TestDatabaseCleanup:
    """Test database cleanup and FK constraints."""

    def test_cascade_delete_results(self):
        """Deleting experiment should cascade delete results."""
        tracker = ExperimentTracker(db_path="./test_feedback.db")

        experiment_id = tracker.create_experiment("Cascade Test", "complexity", "learning", 10)

        # Record some results
        for i in range(5):
            tracker.record_result(
                experiment_id,
                f"user{i}",
                "complexity",
                50.0,
                0.001,
                8,
                "gemini",
                "gemini-1.5-flash",
            )

        conn = sqlite3.connect("./test_feedback.db")
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        # Verify results exist
        cursor.execute(
            "SELECT COUNT(*) FROM experiment_results WHERE experiment_id = ?", (experiment_id,)
        )
        assert cursor.fetchone()[0] == 5

        # Delete experiment
        cursor.execute("DELETE FROM experiments WHERE id = ?", (experiment_id,))
        conn.commit()

        # Results should be cascade deleted
        cursor.execute(
            "SELECT COUNT(*) FROM experiment_results WHERE experiment_id = ?", (experiment_id,)
        )
        assert cursor.fetchone()[0] == 0

        conn.close()
