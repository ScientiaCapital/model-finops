"""Tests for routing data models."""
import pytest
from app.routing.models import RoutingDecision, RoutingContext


def test_routing_decision_creation():
    """Test RoutingDecision can be created with required fields."""
    decision = RoutingDecision(
        provider="gemini",
        model="gemini-flash",
        confidence="high",
        strategy_used="learning",
        reasoning="Test reasoning",
        fallback_used=False,
        metadata={"pattern": "code"}
    )

    assert decision.provider == "gemini"
    assert decision.model == "gemini-flash"
    assert decision.confidence == "high"
    assert decision.strategy_used == "learning"
    assert decision.fallback_used is False
    assert decision.metadata["pattern"] == "code"


def test_routing_context_defaults():
    """Test RoutingContext has sensible defaults."""
    context = RoutingContext(prompt="Test prompt")

    assert context.prompt == "Test prompt"
    assert context.user_id is None
    assert context.available_providers == [
        "gemini", "claude", "openrouter",
        "ollama", "deepseek", "glm", "qwen",
    ]
    assert context.max_cost is None


def test_routing_context_custom_providers():
    """Test RoutingContext accepts custom provider list."""
    context = RoutingContext(
        prompt="Test",
        available_providers=["gemini"]
    )

    assert context.available_providers == ["gemini"]
