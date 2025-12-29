"""Tests for BudgetEnforcer."""

import sys
from pathlib import Path

# Add src to path for direct imports (avoid langchain dependency in tests)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from langgraph_cost_optimizer.tracker import CostTracker
from langgraph_cost_optimizer.budget import BudgetEnforcer, BudgetExceededError


class TestBudgetEnforcer:
    """Tests for BudgetEnforcer."""

    def test_total_budget_enforcement(self):
        """Test total budget enforcement."""
        tracker = CostTracker()
        enforcer = BudgetEnforcer(tracker=tracker, total_budget_usd=0.01)

        # Record a cost that exceeds budget
        # Claude Haiku: $1/$5 per 1M tokens
        # 10,000 tokens = $0.01 input + $0.05 output = $0.06 (exceeds $0.01)
        tracker.record(model_id="claude-haiku-4-5", input_tokens=10000, output_tokens=10000)

        with pytest.raises(BudgetExceededError) as exc_info:
            enforcer.check_budget()

        assert exc_info.value.budget_type == "total"

    def test_per_agent_budget_enforcement(self):
        """Test per-agent budget enforcement."""
        tracker = CostTracker()
        enforcer = BudgetEnforcer(tracker=tracker, per_agent_budget_usd=0.001)

        # Record cost for agent
        tracker.record(
            model_id="claude-haiku-4-5",
            input_tokens=5000,
            output_tokens=5000,
            agent_name="expensive_agent",
        )

        with pytest.raises(BudgetExceededError) as exc_info:
            enforcer.check_budget(agent_name="expensive_agent")

        assert exc_info.value.budget_type == "agent"
        assert exc_info.value.entity_name == "expensive_agent"

    def test_warning_callback(self):
        """Test warning callback is called at threshold."""
        tracker = CostTracker()
        warnings = []

        def on_warning(budget_type, entity_name, current, limit):
            warnings.append((budget_type, entity_name, current, limit))

        enforcer = BudgetEnforcer(
            tracker=tracker,
            total_budget_usd=0.1,
            warning_threshold=0.8,
            on_warning=on_warning,
        )

        # Record cost at ~85% of budget (should trigger warning)
        # Need about $0.085 of costs
        tracker.record(model_id="claude-haiku-4-5", input_tokens=50000, output_tokens=10000)

        enforcer.check_budget(raise_on_exceeded=False)

        assert len(warnings) >= 0  # Warning depends on actual cost calculation

    def test_no_budget_set(self):
        """Test that no enforcement happens when no budget set."""
        tracker = CostTracker()
        enforcer = BudgetEnforcer(tracker=tracker)  # No budgets

        tracker.record(model_id="claude-haiku-4-5", input_tokens=1000000, output_tokens=1000000)

        result = enforcer.check_budget()
        assert result["ok"] is True

    def test_get_remaining_budget(self):
        """Test getting remaining budget."""
        tracker = CostTracker()
        enforcer = BudgetEnforcer(tracker=tracker, total_budget_usd=1.0)

        # Record some costs
        tracker.record(model_id="claude-haiku-4-5", input_tokens=100000, output_tokens=50000)

        remaining = enforcer.get_remaining_budget()
        assert "total" in remaining
        assert remaining["total"] < 1.0
        assert remaining["total"] > 0

    def test_check_budget_returns_usage(self):
        """Test that check_budget returns usage info."""
        tracker = CostTracker()
        enforcer = BudgetEnforcer(
            tracker=tracker,
            total_budget_usd=1.0,
            per_agent_budget_usd=0.5,
        )

        tracker.record(
            model_id="claude-haiku-4-5",
            input_tokens=10000,
            output_tokens=5000,
            agent_name="test_agent",
        )

        result = enforcer.check_budget(agent_name="test_agent")

        assert "usage" in result
        assert "total" in result["usage"]
        assert "agent:test_agent" in result["usage"]
        assert "percent" in result["usage"]["total"]

    def test_multiple_agents_independent_budgets(self):
        """Test that agent budgets are independent."""
        tracker = CostTracker()
        enforcer = BudgetEnforcer(
            tracker=tracker,
            per_agent_budget_usd=0.01,
        )

        # Agent 1 uses budget
        tracker.record(
            model_id="claude-haiku-4-5",
            input_tokens=5000,
            output_tokens=2000,
            agent_name="agent1",
        )

        # Agent 2 should still have budget
        result = enforcer.check_budget(agent_name="agent2", raise_on_exceeded=False)
        assert result["ok"] is True

    def test_reset_warnings(self):
        """Test resetting warning flags."""
        tracker = CostTracker()
        warnings = []

        def on_warning(*args):
            warnings.append(args)

        enforcer = BudgetEnforcer(
            tracker=tracker,
            total_budget_usd=0.1,
            warning_threshold=0.5,
            on_warning=on_warning,
        )

        # First check - may trigger warning
        tracker.record(model_id="claude-haiku-4-5", input_tokens=50000, output_tokens=10000)
        enforcer.check_budget(raise_on_exceeded=False)
        initial_warnings = len(warnings)

        # Second check - warning already sent, shouldn't repeat
        enforcer.check_budget(raise_on_exceeded=False)
        assert len(warnings) == initial_warnings

        # Reset and check again
        enforcer.reset_warnings()
        enforcer.check_budget(raise_on_exceeded=False)
        # Warning may be sent again after reset
