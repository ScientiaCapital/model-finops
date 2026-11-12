"""Tests for routing strategy interface."""

import pytest

from app.routing.models import RoutingContext, RoutingDecision
from app.routing.strategy import RoutingStrategy


class ConcreteStrategy(RoutingStrategy):
    """Concrete implementation for testing."""

    def route(self, prompt: str, context: RoutingContext) -> RoutingDecision:
        return RoutingDecision(
            provider="test",
            model="test-model",
            confidence="high",
            strategy_used="test",
            reasoning="test routing",
            fallback_used=False,
            metadata={},
        )

    def get_name(self) -> str:
        return "test_strategy"


def test_routing_strategy_abstract():
    """Test RoutingStrategy cannot be instantiated directly."""
    with pytest.raises(TypeError):
        RoutingStrategy()


def test_concrete_strategy_implementation():
    """Test concrete strategy can be instantiated and used."""
    strategy = ConcreteStrategy()
    context = RoutingContext(prompt="test")

    decision = strategy.route("test prompt", context)

    assert decision.provider == "test"
    assert decision.strategy_used == "test"
    assert strategy.get_name() == "test_strategy"
