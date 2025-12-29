"""Tests for CostTracker."""

import sys
from pathlib import Path

# Add src to path for direct imports (avoid langchain dependency in tests)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from datetime import datetime, timezone, timedelta

from langgraph_cost_optimizer.tracker import CostTracker, CostRecord
from langgraph_cost_optimizer.providers import PROVIDER_PRICING


class TestCostRecord:
    """Tests for CostRecord dataclass."""

    def test_create_record(self):
        """Test creating a record with calculated cost."""
        record = CostRecord.create(
            model_id="claude-sonnet-4-5",
            input_tokens=1000,
            output_tokens=500,
            agent_name="researcher",
        )

        assert record.model_id == "claude-sonnet-4-5"
        assert record.input_tokens == 1000
        assert record.output_tokens == 500
        assert record.agent_name == "researcher"
        assert record.cost_usd > 0  # Calculated from pricing
        assert record.id is not None
        assert record.timestamp is not None

    def test_cost_calculation(self):
        """Test that cost is calculated correctly."""
        # Claude Sonnet 4.5: $3.00/$15.00 per 1M tokens
        record = CostRecord.create(
            model_id="claude-sonnet-4-5",
            input_tokens=1_000_000,  # 1M input
            output_tokens=1_000_000,  # 1M output
        )

        expected_cost = 3.00 + 15.00  # $18.00 total
        assert abs(record.cost_usd - expected_cost) < 0.001


class TestCostTracker:
    """Tests for CostTracker."""

    def test_record_cost(self):
        """Test recording a single cost."""
        tracker = CostTracker()

        record = tracker.record(
            model_id="claude-haiku-4-5",
            input_tokens=500,
            output_tokens=200,
            agent_name="assistant",
        )

        assert len(tracker) == 1
        assert tracker.total_cost > 0
        assert tracker.total_tokens == 700

    def test_multiple_records(self):
        """Test recording multiple costs."""
        tracker = CostTracker()

        tracker.record(model_id="claude-haiku-4-5", input_tokens=500, output_tokens=200)
        tracker.record(model_id="claude-sonnet-4-5", input_tokens=1000, output_tokens=500)
        tracker.record(model_id="deepseek/deepseek-chat", input_tokens=2000, output_tokens=1000)

        assert len(tracker) == 3
        assert tracker.total_tokens == 5200

    def test_cost_by_agent(self):
        """Test getting costs grouped by agent."""
        tracker = CostTracker()

        tracker.record(model_id="claude-haiku-4-5", input_tokens=500, output_tokens=200, agent_name="researcher")
        tracker.record(model_id="claude-haiku-4-5", input_tokens=300, output_tokens=100, agent_name="researcher")
        tracker.record(model_id="claude-haiku-4-5", input_tokens=1000, output_tokens=500, agent_name="writer")

        by_agent = tracker.get_cost_by_agent()

        assert "researcher" in by_agent
        assert "writer" in by_agent
        assert by_agent["researcher"] > 0
        assert by_agent["writer"] > 0

    def test_cost_by_node(self):
        """Test getting costs grouped by node."""
        tracker = CostTracker()

        tracker.record(model_id="claude-haiku-4-5", input_tokens=500, output_tokens=200, node_name="analyze")
        tracker.record(model_id="claude-haiku-4-5", input_tokens=1000, output_tokens=500, node_name="generate")

        by_node = tracker.get_cost_by_node()

        assert "analyze" in by_node
        assert "generate" in by_node

    def test_cost_by_model(self):
        """Test getting costs grouped by model."""
        tracker = CostTracker()

        tracker.record(model_id="claude-haiku-4-5", input_tokens=500, output_tokens=200)
        tracker.record(model_id="claude-sonnet-4-5", input_tokens=500, output_tokens=200)
        tracker.record(model_id="claude-haiku-4-5", input_tokens=500, output_tokens=200)

        by_model = tracker.get_cost_by_model()

        assert "claude-haiku-4-5" in by_model
        assert "claude-sonnet-4-5" in by_model

    def test_get_summary(self):
        """Test getting comprehensive summary."""
        tracker = CostTracker()

        tracker.record(model_id="claude-haiku-4-5", input_tokens=500, output_tokens=200, agent_name="a1")
        tracker.record(model_id="claude-sonnet-4-5", input_tokens=1000, output_tokens=500, agent_name="a2")

        summary = tracker.get_summary()

        assert "total_cost_usd" in summary
        assert "total_tokens" in summary
        assert "num_calls" in summary
        assert "by_agent" in summary
        assert "by_model" in summary
        assert summary["num_calls"] == 2

    def test_get_records_filtered(self):
        """Test filtering records."""
        tracker = CostTracker()

        tracker.record(model_id="claude-haiku-4-5", input_tokens=500, output_tokens=200, agent_name="a1")
        tracker.record(model_id="claude-sonnet-4-5", input_tokens=1000, output_tokens=500, agent_name="a2")
        tracker.record(model_id="claude-haiku-4-5", input_tokens=300, output_tokens=100, agent_name="a1")

        # Filter by agent
        a1_records = tracker.get_records(agent_name="a1")
        assert len(a1_records) == 2

        # Filter by model
        haiku_records = tracker.get_records(model_id="claude-haiku-4-5")
        assert len(haiku_records) == 2

    def test_reset(self):
        """Test resetting tracker."""
        tracker = CostTracker()

        tracker.record(model_id="claude-haiku-4-5", input_tokens=500, output_tokens=200)
        assert len(tracker) == 1

        tracker.reset()
        assert len(tracker) == 0
        assert tracker.total_cost == 0

    def test_thread_safety(self):
        """Test that tracker is thread-safe."""
        import threading

        tracker = CostTracker()
        errors = []

        def record_costs():
            try:
                for _ in range(100):
                    tracker.record(
                        model_id="claude-haiku-4-5",
                        input_tokens=100,
                        output_tokens=50,
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_costs) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(tracker) == 500  # 5 threads x 100 records
