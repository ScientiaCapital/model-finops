"""
Tests for Experiment API Endpoints

This test suite validates the A/B testing experiment API endpoints:
- POST /experiments - Create new experiment
- GET /experiments/active - List active experiments
- POST /experiments/{id}/complete - Mark experiment complete
- GET /experiments/{id}/assign/{user_id} - Assign user to group
- POST /experiments/{id}/results - Record experiment result
- GET /experiments/{id}/summary - Get aggregated statistics
- GET /experiments/{id}/progress - Get experiment progress
- POST /experiments/{id}/analyze - Run statistical analysis
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestCreateExperiment:
    """Test POST /experiments endpoint."""

    def test_create_experiment_success(self):
        """Create a new A/B test experiment."""
        response = client.post(
            "/experiments",
            json={
                "name": "Test Complexity vs Learning",
                "control_strategy": "complexity",
                "test_strategy": "learning",
                "sample_size": 100,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert "experiment_id" in data
        assert data["experiment_id"] > 0
        assert data["name"] == "Test Complexity vs Learning"
        assert data["status"] == "active"

    def test_create_experiment_validation_error(self):
        """Reject experiment with invalid strategies."""
        response = client.post(
            "/experiments",
            json={
                "name": "Invalid Test",
                "control_strategy": "invalid_strategy",
                "test_strategy": "learning",
                "sample_size": 100,
            },
        )

        assert response.status_code == 422  # Validation error

    def test_create_experiment_same_strategies(self):
        """Reject experiment with identical control and test strategies."""
        response = client.post(
            "/experiments",
            json={
                "name": "Same Strategy Test",
                "control_strategy": "complexity",
                "test_strategy": "complexity",
                "sample_size": 100,
            },
        )

        assert response.status_code == 400
        assert "different" in response.json()["detail"].lower()

    def test_create_experiment_negative_sample_size(self):
        """Reject experiment with negative sample size."""
        response = client.post(
            "/experiments",
            json={
                "name": "Negative Sample Test",
                "control_strategy": "complexity",
                "test_strategy": "learning",
                "sample_size": -10,
            },
        )

        assert response.status_code == 422


class TestGetActiveExperiments:
    """Test GET /experiments/active endpoint."""

    def test_get_active_experiments_empty(self):
        """List active experiments when none exist."""
        response = client.get("/experiments/active")

        assert response.status_code == 200
        data = response.json()
        assert "experiments" in data
        assert isinstance(data["experiments"], list)

    def test_get_active_experiments_with_data(self):
        """List active experiments when some exist."""
        # Create test experiments
        client.post(
            "/experiments",
            json={
                "name": "Experiment 1",
                "control_strategy": "complexity",
                "test_strategy": "learning",
                "sample_size": 50,
            },
        )
        client.post(
            "/experiments",
            json={
                "name": "Experiment 2",
                "control_strategy": "learning",
                "test_strategy": "hybrid",
                "sample_size": 100,
            },
        )

        response = client.get("/experiments/active")

        assert response.status_code == 200
        data = response.json()
        assert len(data["experiments"]) >= 2
        # Verify structure
        exp = data["experiments"][0]
        assert "id" in exp
        assert "name" in exp
        assert "control_strategy" in exp
        assert "test_strategy" in exp


class TestCompleteExperiment:
    """Test POST /experiments/{id}/complete endpoint."""

    def test_complete_experiment_success(self):
        """Mark experiment as completed."""
        # Create experiment
        create_response = client.post(
            "/experiments",
            json={
                "name": "Complete Test",
                "control_strategy": "complexity",
                "test_strategy": "learning",
                "sample_size": 10,
            },
        )
        experiment_id = create_response.json()["experiment_id"]

        # Complete it
        response = client.post(
            f"/experiments/{experiment_id}/complete", json={"winner": "learning"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["winner"] == "learning"

    def test_complete_experiment_not_found(self):
        """Return 404 for non-existent experiment."""
        response = client.post("/experiments/99999/complete", json={"winner": "complexity"})

        assert response.status_code == 404


class TestAssignUser:
    """Test GET /experiments/{id}/assign/{user_id} endpoint."""

    def test_assign_user_to_experiment(self):
        """Assign user to control or test group."""
        # Create experiment
        create_response = client.post(
            "/experiments",
            json={
                "name": "Assignment Test",
                "control_strategy": "complexity",
                "test_strategy": "learning",
                "sample_size": 50,
            },
        )
        experiment_id = create_response.json()["experiment_id"]

        # Assign user
        response = client.get(f"/experiments/{experiment_id}/assign/user123")

        assert response.status_code == 200
        data = response.json()
        assert "strategy" in data
        assert data["strategy"] in ["complexity", "learning"]
        assert data["user_id"] == "user123"

    def test_assign_user_deterministic(self):
        """Same user gets same strategy on multiple calls."""
        # Create experiment
        create_response = client.post(
            "/experiments",
            json={
                "name": "Deterministic Test",
                "control_strategy": "complexity",
                "test_strategy": "learning",
                "sample_size": 50,
            },
        )
        experiment_id = create_response.json()["experiment_id"]

        # Assign same user multiple times
        response1 = client.get(f"/experiments/{experiment_id}/assign/user456")
        response2 = client.get(f"/experiments/{experiment_id}/assign/user456")
        response3 = client.get(f"/experiments/{experiment_id}/assign/user456")

        strategy1 = response1.json()["strategy"]
        strategy2 = response2.json()["strategy"]
        strategy3 = response3.json()["strategy"]

        assert strategy1 == strategy2 == strategy3

    def test_assign_user_to_nonexistent_experiment(self):
        """Return 404 for non-existent experiment."""
        response = client.get("/experiments/99999/assign/user789")

        assert response.status_code == 404


class TestRecordResult:
    """Test POST /experiments/{id}/results endpoint."""

    def test_record_result_success(self):
        """Record an experiment result."""
        # Create experiment
        create_response = client.post(
            "/experiments",
            json={
                "name": "Result Test",
                "control_strategy": "complexity",
                "test_strategy": "learning",
                "sample_size": 10,
            },
        )
        experiment_id = create_response.json()["experiment_id"]

        # Record result
        response = client.post(
            f"/experiments/{experiment_id}/results",
            json={
                "user_id": "user123",
                "strategy_assigned": "complexity",
                "latency_ms": 45.5,
                "cost_usd": 0.0012,
                "quality_score": 8,
                "provider": "gemini",
                "model": "gemini-1.5-flash",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert "result_id" in data
        assert data["result_id"] > 0

    def test_record_result_validation_error(self):
        """Reject result with invalid data."""
        # Create experiment
        create_response = client.post(
            "/experiments",
            json={
                "name": "Validation Test",
                "control_strategy": "complexity",
                "test_strategy": "learning",
                "sample_size": 10,
            },
        )
        experiment_id = create_response.json()["experiment_id"]

        # Record result with negative latency
        response = client.post(
            f"/experiments/{experiment_id}/results",
            json={
                "user_id": "user123",
                "strategy_assigned": "complexity",
                "latency_ms": -45.5,  # Invalid
                "cost_usd": 0.0012,
                "quality_score": 8,
                "provider": "gemini",
                "model": "gemini-1.5-flash",
            },
        )

        assert response.status_code == 422


class TestGetSummary:
    """Test GET /experiments/{id}/summary endpoint."""

    def test_get_summary_with_data(self):
        """Get aggregated statistics for experiment."""
        # Create experiment
        create_response = client.post(
            "/experiments",
            json={
                "name": "Summary Test",
                "control_strategy": "complexity",
                "test_strategy": "learning",
                "sample_size": 20,
            },
        )
        experiment_id = create_response.json()["experiment_id"]

        # Record some results
        for i in range(5):
            client.post(
                f"/experiments/{experiment_id}/results",
                json={
                    "user_id": f"control_user{i}",
                    "strategy_assigned": "complexity",
                    "latency_ms": 50.0,
                    "cost_usd": 0.002,
                    "quality_score": 7,
                    "provider": "gemini",
                    "model": "gemini-1.5-flash",
                },
            )

        for i in range(5):
            client.post(
                f"/experiments/{experiment_id}/results",
                json={
                    "user_id": f"test_user{i}",
                    "strategy_assigned": "learning",
                    "latency_ms": 35.0,
                    "cost_usd": 0.0015,
                    "quality_score": 9,
                    "provider": "gemini",
                    "model": "gemini-1.5-flash",
                },
            )

        # Get summary
        response = client.get(f"/experiments/{experiment_id}/summary")

        assert response.status_code == 200
        data = response.json()
        assert "control" in data
        assert "test" in data
        assert data["control"]["count"] == 5
        assert data["test"]["count"] == 5
        assert data["control"]["avg_latency_ms"] == 50.0
        assert data["test"]["avg_latency_ms"] == 35.0

    def test_get_summary_empty(self):
        """Get summary for experiment with no results."""
        # Create experiment
        create_response = client.post(
            "/experiments",
            json={
                "name": "Empty Summary Test",
                "control_strategy": "complexity",
                "test_strategy": "learning",
                "sample_size": 10,
            },
        )
        experiment_id = create_response.json()["experiment_id"]

        response = client.get(f"/experiments/{experiment_id}/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["control"]["count"] == 0
        assert data["test"]["count"] == 0


class TestGetProgress:
    """Test GET /experiments/{id}/progress endpoint."""

    def test_get_progress(self):
        """Get progress toward sample size goal."""
        # Create experiment
        create_response = client.post(
            "/experiments",
            json={
                "name": "Progress Test",
                "control_strategy": "complexity",
                "test_strategy": "learning",
                "sample_size": 10,
            },
        )
        experiment_id = create_response.json()["experiment_id"]

        # Record 6 results
        for i in range(6):
            client.post(
                f"/experiments/{experiment_id}/results",
                json={
                    "user_id": f"user{i}",
                    "strategy_assigned": "complexity",
                    "latency_ms": 50.0,
                    "cost_usd": 0.001,
                    "quality_score": 8,
                    "provider": "gemini",
                    "model": "gemini-1.5-flash",
                },
            )

        response = client.get(f"/experiments/{experiment_id}/progress")

        assert response.status_code == 200
        data = response.json()
        assert data["sample_size"] == 10
        assert data["total_results"] == 6
        assert data["completion_percentage"] == 60.0
        assert data["is_complete"] is False


class TestAnalyzeExperiment:
    """Test POST /experiments/{id}/analyze endpoint."""

    def test_analyze_experiment_with_sufficient_data(self):
        """Run statistical analysis on experiment."""
        # Create experiment
        create_response = client.post(
            "/experiments",
            json={
                "name": "Analysis Test",
                "control_strategy": "complexity",
                "test_strategy": "learning",
                "sample_size": 100,
            },
        )
        experiment_id = create_response.json()["experiment_id"]

        # Record 60 results (30 per group)
        for i in range(30):
            client.post(
                f"/experiments/{experiment_id}/results",
                json={
                    "user_id": f"control_user{i}",
                    "strategy_assigned": "complexity",
                    "latency_ms": 50.0 + i * 0.1,
                    "cost_usd": 0.002,
                    "quality_score": 7,
                    "provider": "gemini",
                    "model": "gemini-1.5-flash",
                },
            )

        for i in range(30):
            client.post(
                f"/experiments/{experiment_id}/results",
                json={
                    "user_id": f"test_user{i}",
                    "strategy_assigned": "learning",
                    "latency_ms": 35.0 + i * 0.1,
                    "cost_usd": 0.0015,
                    "quality_score": 9,
                    "provider": "gemini",
                    "model": "gemini-1.5-flash",
                },
            )

        # Analyze
        response = client.post(f"/experiments/{experiment_id}/analyze")

        assert response.status_code == 200
        data = response.json()
        assert "overall_winner" in data
        assert "confidence_level" in data
        assert "recommendation" in data
        assert data["valid"] is True

    def test_analyze_experiment_insufficient_data(self):
        """Return error when insufficient data for analysis."""
        # Create experiment
        create_response = client.post(
            "/experiments",
            json={
                "name": "Insufficient Data Test",
                "control_strategy": "complexity",
                "test_strategy": "learning",
                "sample_size": 10,
            },
        )
        experiment_id = create_response.json()["experiment_id"]

        # Record only 5 results (too few)
        for i in range(5):
            client.post(
                f"/experiments/{experiment_id}/results",
                json={
                    "user_id": f"user{i}",
                    "strategy_assigned": "complexity",
                    "latency_ms": 50.0,
                    "cost_usd": 0.001,
                    "quality_score": 8,
                    "provider": "gemini",
                    "model": "gemini-1.5-flash",
                },
            )

        response = client.post(f"/experiments/{experiment_id}/analyze")

        assert response.status_code == 400
        data = response.json()
        assert "insufficient" in data["detail"].lower()
