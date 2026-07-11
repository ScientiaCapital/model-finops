"""Tests for RoutingEngine - the main orchestrator for routing decisions."""
import pytest
from unittest.mock import patch
from app.routing.engine import RoutingEngine
from app.routing.models import RoutingContext, RoutingDecision


@pytest.fixture
def engine():
    """Create a routing engine instance for testing."""
    return RoutingEngine(db_path="test.db")


def test_route_with_auto_route_false_uses_complexity(engine):
    """Test routing with auto_route=False uses complexity strategy."""
    decision = engine.route(
        prompt="What is Python?",
        auto_route=False
    )

    # Should use complexity strategy
    assert decision.strategy_used == "complexity"

    # Should return valid provider
    assert decision.provider in ["gemini", "claude", "openrouter"]

    # Should have confidence level
    assert decision.confidence in ["high", "medium", "low"]

    # Should have model specified
    assert decision.model is not None
    assert isinstance(decision.model, str)


def test_route_with_auto_route_true_uses_hybrid(engine):
    """Test routing with auto_route=True uses hybrid strategy."""
    decision = engine.route(
        prompt="What is Python?",
        auto_route=True
    )

    # Should use hybrid strategy
    assert decision.strategy_used == "hybrid"

    # Should return valid provider
    assert decision.provider in ["gemini", "claude", "openrouter"]

    # Should have confidence level
    assert decision.confidence in ["high", "medium", "low"]

    # Should have model specified
    assert decision.model is not None


def test_default_auto_route_is_false(engine):
    """Test that default behavior is auto_route=False (complexity)."""
    decision = engine.route(prompt="What is Python?")

    # Should use complexity by default (safe)
    assert decision.strategy_used == "complexity"

    # Should return valid provider
    assert decision.provider in ["gemini", "claude", "openrouter"]
    assert decision.model is not None


def test_validation_with_invalid_decision(engine):
    """Test that invalid decisions trigger fallback."""
    # Mock hybrid strategy to return invalid decision
    with patch.object(engine.strategies['hybrid'], 'route') as mock_route:
        mock_route.return_value = RoutingDecision(
            provider="invalid_provider",  # Invalid!
            model="test-model",
            confidence="high",
            strategy_used="hybrid",
            reasoning="Test",
            fallback_used=False
        )

        # Should fallback to complexity
        decision = engine.route(prompt="Test", auto_route=True)

        assert decision.fallback_used is True
        assert decision.strategy_used == "complexity"
        assert "fallback_reason" in decision.metadata


def test_route_with_context():
    """Test routing with explicit context object."""
    engine = RoutingEngine(db_path="test.db")

    # Create context with user preferences
    context = RoutingContext(
        prompt="What is AI?",
        user_id="test_user_123",
        max_cost=0.01
    )

    decision = engine.route(
        prompt="What is AI?",
        auto_route=False,
        context=context
    )

    # Should use provided context
    assert decision.provider in ["gemini", "claude", "openrouter"]
    assert decision.strategy_used == "complexity"


def test_route_creates_default_context_when_none_provided(engine):
    """Test that engine creates default context if none provided."""
    # Route without context
    decision = engine.route(prompt="Test prompt", auto_route=False)

    # Should still work and return valid decision
    assert decision.provider in ["gemini", "claude", "openrouter"]
    assert decision.strategy_used == "complexity"
    assert decision.model is not None


# =============================================================================
# New providers must be valid routing targets (Ollama/DeepSeek/GLM/Qwen)
# =============================================================================

@pytest.mark.parametrize("provider", ["ollama", "deepseek", "glm", "qwen"])
def test_new_providers_are_valid(provider):
    """Engine should accept the new providers as valid routing targets."""
    assert provider in RoutingEngine.VALID_PROVIDERS


def test_route_accepts_deepseek_without_fallback(engine):
    """A decision routing to DeepSeek should pass validation, not fall back."""
    context = RoutingContext(prompt="Hello", available_providers=["deepseek"])

    decision = engine.route(prompt="Hello", auto_route=False, context=context)

    assert decision.provider == "deepseek"
    assert decision.fallback_used is False


def test_route_accepts_ollama_without_fallback(engine):
    """A decision routing to Ollama should pass validation, not fall back."""
    context = RoutingContext(prompt="Hello", available_providers=["ollama"])

    decision = engine.route(prompt="Hello", auto_route=False, context=context)

    assert decision.provider == "ollama"
    assert decision.fallback_used is False
