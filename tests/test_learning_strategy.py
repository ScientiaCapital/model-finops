"""Tests for LearningStrategy."""

from app.routing.models import RoutingContext
from app.routing.strategy import LearningStrategy


def test_learning_strategy_uses_analyzer(tmp_path):
    """Test LearningStrategy queries QueryPatternAnalyzer."""
    db_path = tmp_path / "test.db"
    strategy = LearningStrategy(db_path=str(db_path))
    context = RoutingContext(prompt="Debug Python code")

    decision = strategy.route("Debug Python code", context)

    assert decision.strategy_used == "learning"
    assert decision.confidence in ["high", "medium", "low"]
    assert "pattern" in decision.metadata
    assert "complexity" in decision.metadata


def test_learning_strategy_includes_quality_cost(tmp_path):
    """Test decision includes quality and cost metadata."""
    db_path = tmp_path / "test.db"
    strategy = LearningStrategy(db_path=str(db_path))
    context = RoutingContext(prompt="Test query")

    decision = strategy.route("Test query", context)

    # May be None if no training data, but key should exist
    assert "quality_score" in decision.metadata
    assert "cost_estimate" in decision.metadata


def test_learning_strategy_name():
    """Test strategy returns correct name."""
    strategy = LearningStrategy()
    assert strategy.get_name() == "learning"
