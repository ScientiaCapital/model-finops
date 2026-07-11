"""Tests for ComplexityStrategy."""
import pytest
from app.routing.strategy import ComplexityStrategy
from app.routing.models import RoutingContext


def test_complexity_strategy_simple_prompt():
    """Test simple prompt routes to Gemini."""
    strategy = ComplexityStrategy()
    context = RoutingContext(prompt="Hello")

    decision = strategy.route("Hello", context)

    assert decision.provider == "gemini"
    assert decision.model == "gemini-1.5-flash"
    assert decision.confidence == "medium"
    assert decision.strategy_used == "complexity"
    assert "complexity" in decision.metadata
    assert decision.fallback_used is False


def test_complexity_strategy_moderate_prompt():
    """Test moderate prompt routes to Claude Haiku."""
    strategy = ComplexityStrategy()
    context = RoutingContext(prompt="Explain how HTTP works")

    decision = strategy.route("Explain how HTTP works", context)

    assert decision.provider == "claude"
    assert decision.model == "claude-3-haiku-20240307"
    assert decision.confidence == "medium"
    assert decision.fallback_used is False


def test_complexity_strategy_complex_prompt():
    """Test complex prompt routes to Claude Sonnet."""
    strategy = ComplexityStrategy()
    long_prompt = "Analyze the architectural trade-offs between " * 10
    context = RoutingContext(prompt=long_prompt)

    decision = strategy.route(long_prompt, context)

    assert decision.provider == "claude"
    assert decision.model == "claude-3-5-sonnet-20241022"
    assert decision.fallback_used is False


def test_complexity_strategy_simple_fallback_to_openrouter():
    """Test simple prompt falls back to OpenRouter when Gemini unavailable."""
    strategy = ComplexityStrategy()
    context = RoutingContext(
        prompt="Hello",
        available_providers=["openrouter"]
    )

    decision = strategy.route("Hello", context)

    assert decision.provider == "openrouter"
    assert decision.model == "google/gemini-flash-1.5"
    assert decision.fallback_used is False


def test_complexity_strategy_simple_fallback_to_claude():
    """Test simple prompt falls back to Claude when Gemini and OpenRouter unavailable."""
    strategy = ComplexityStrategy()
    context = RoutingContext(
        prompt="Hello",
        available_providers=["claude"]
    )

    decision = strategy.route("Hello", context)

    assert decision.provider == "claude"
    assert decision.model == "claude-3-haiku-20240307"
    assert decision.fallback_used is False


def test_complexity_strategy_moderate_fallback_to_gemini():
    """Test moderate prompt falls back to Gemini when Claude unavailable."""
    strategy = ComplexityStrategy()
    context = RoutingContext(
        prompt="Explain how HTTP works",
        available_providers=["gemini", "openrouter"]
    )

    decision = strategy.route("Explain how HTTP works", context)

    assert decision.provider == "gemini"
    assert decision.model == "gemini-1.5-flash"
    assert decision.fallback_used is False


def test_complexity_strategy_complex_fallback_to_gemini():
    """Test complex prompt falls back to Gemini when Claude unavailable."""
    strategy = ComplexityStrategy()
    long_prompt = "Analyze the architectural trade-offs between " * 10
    context = RoutingContext(
        prompt=long_prompt,
        available_providers=["gemini", "openrouter"]
    )

    decision = strategy.route(long_prompt, context)

    assert decision.provider == "gemini"
    assert decision.model == "gemini-1.5-flash"
    assert decision.fallback_used is False


def test_complexity_strategy_absolute_fallback():
    """Test absolute fallback when preferred providers unavailable."""
    strategy = ComplexityStrategy()
    context = RoutingContext(
        prompt="Test prompt",
        available_providers=["some_other_provider"]
    )

    decision = strategy.route("Test prompt", context)

    assert decision.provider == "some_other_provider"
    assert decision.model == "default"
    assert decision.fallback_used is True


def test_complexity_strategy_no_providers():
    """Test error when no providers available."""
    strategy = ComplexityStrategy()
    context = RoutingContext(
        prompt="Test prompt",
        available_providers=[]
    )

    with pytest.raises(ValueError, match="No providers available"):
        strategy.route("Test prompt", context)


def test_complexity_strategy_name():
    """Test strategy returns correct name."""
    strategy = ComplexityStrategy()
    assert strategy.get_name() == "complexity"


# =============================================================================
# New provider selectability (Ollama, DeepSeek, GLM, Qwen)
# =============================================================================

def test_complexity_strategy_simple_selects_ollama():
    """Simple prompt should select Ollama when it's the only provider."""
    strategy = ComplexityStrategy()
    context = RoutingContext(prompt="Hello", available_providers=["ollama"])

    decision = strategy.route("Hello", context)

    assert decision.provider == "ollama"
    assert decision.model == "llama3.2"
    assert decision.fallback_used is False


def test_complexity_strategy_simple_selects_deepseek():
    """Simple prompt should select DeepSeek when it's the only provider."""
    strategy = ComplexityStrategy()
    context = RoutingContext(prompt="Hello", available_providers=["deepseek"])

    decision = strategy.route("Hello", context)

    assert decision.provider == "deepseek"
    assert decision.model == "deepseek-chat"
    assert decision.fallback_used is False


def test_complexity_strategy_moderate_selects_qwen():
    """Moderate prompt should select Qwen when it's the only provider."""
    strategy = ComplexityStrategy()
    context = RoutingContext(
        prompt="Explain how HTTP works",
        available_providers=["qwen"]
    )

    decision = strategy.route("Explain how HTTP works", context)

    assert decision.provider == "qwen"
    assert decision.model == "qwen-plus"
    assert decision.fallback_used is False


def test_complexity_strategy_complex_selects_glm():
    """Complex prompt should select GLM when it's the only provider."""
    strategy = ComplexityStrategy()
    long_prompt = "Analyze the architectural trade-offs between " * 10
    context = RoutingContext(prompt=long_prompt, available_providers=["glm"])

    decision = strategy.route(long_prompt, context)

    assert decision.provider == "glm"
    assert decision.model == "glm-4.7"
    assert decision.fallback_used is False


def test_complexity_strategy_default_unchanged_by_new_providers():
    """Default provider list should still prefer gemini/claude, not new providers."""
    strategy = ComplexityStrategy()
    context = RoutingContext(prompt="Hello")  # default available_providers

    decision = strategy.route("Hello", context)

    # New providers must not hijack the established simple-tier default
    assert decision.provider == "gemini"
    assert decision.model == "gemini-1.5-flash"
