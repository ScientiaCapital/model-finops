"""Tests for provider pricing."""

import sys
from pathlib import Path

# Add src to path for direct imports (avoid langchain dependency in tests)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from langgraph_cost_optimizer.providers import (
    PROVIDER_PRICING,
    ModelPricing,
    get_model_pricing,
    calculate_cost,
    get_cheapest_model,
)


class TestProviderPricing:
    """Tests for provider pricing registry."""

    def test_claude_45_models_exist(self):
        """Test that Claude 4.5 models are in registry."""
        assert "claude-opus-4-5" in PROVIDER_PRICING
        assert "claude-sonnet-4-5" in PROVIDER_PRICING
        assert "claude-haiku-4-5" in PROVIDER_PRICING

        # Dated versions
        assert "claude-opus-4-5-20251101" in PROVIDER_PRICING
        assert "claude-sonnet-4-5-20250929" in PROVIDER_PRICING
        assert "claude-haiku-4-5-20251001" in PROVIDER_PRICING

    def test_deepseek_models_exist(self):
        """Test that DeepSeek models are in registry."""
        assert "deepseek/deepseek-chat" in PROVIDER_PRICING
        assert "deepseek/deepseek-r1" in PROVIDER_PRICING

    def test_qwen_models_exist(self):
        """Test that Qwen models are in registry."""
        assert "qwen/qwen-2.5-72b-instruct" in PROVIDER_PRICING
        assert "qwen/qwen-2.5-coder-7b-instruct" in PROVIDER_PRICING

    def test_groq_models_exist(self):
        """Test that Groq models are in registry."""
        assert "llama-3.3-70b-versatile" in PROVIDER_PRICING
        assert "llama-3.1-8b-instant" in PROVIDER_PRICING

    def test_get_model_pricing(self):
        """Test getting pricing for a model."""
        pricing = get_model_pricing("claude-sonnet-4-5")

        assert pricing is not None
        assert isinstance(pricing, ModelPricing)
        assert pricing.input_price == 3.00
        assert pricing.output_price == 15.00
        assert pricing.provider == "anthropic"

    def test_get_model_pricing_unknown(self):
        """Test getting pricing for unknown model."""
        pricing = get_model_pricing("unknown-model-xyz")
        assert pricing is None

    def test_calculate_cost(self):
        """Test cost calculation."""
        # Claude Sonnet 4.5: $3.00/$15.00 per 1M tokens
        cost = calculate_cost("claude-sonnet-4-5", input_tokens=1000, output_tokens=500)

        # Expected: (1000/1M * 3.00) + (500/1M * 15.00) = 0.003 + 0.0075 = 0.0105
        expected = 0.003 + 0.0075
        assert abs(cost - expected) < 0.0001

    def test_calculate_cost_unknown_model(self):
        """Test cost calculation for unknown model raises."""
        with pytest.raises(ValueError, match="Unknown model"):
            calculate_cost("unknown-model", input_tokens=100, output_tokens=50)

    def test_get_cheapest_model(self):
        """Test getting cheapest model."""
        model_id, pricing = get_cheapest_model()

        assert model_id is not None
        assert pricing is not None
        # Should be a cheap model
        assert (pricing.input_price + pricing.output_price) / 2 < 1.0

    def test_get_cheapest_model_with_context_requirement(self):
        """Test getting cheapest model with minimum context."""
        model_id, pricing = get_cheapest_model(min_context=100_000)

        assert pricing.context_window >= 100_000

    def test_get_cheapest_model_by_provider(self):
        """Test getting cheapest model from specific providers."""
        model_id, pricing = get_cheapest_model(providers=["anthropic"])

        assert pricing.provider == "anthropic"

    def test_pricing_has_required_fields(self):
        """Test all pricing entries have required fields."""
        for model_id, pricing in PROVIDER_PRICING.items():
            assert isinstance(pricing.input_price, (int, float)), f"{model_id} missing input_price"
            assert isinstance(pricing.output_price, (int, float)), f"{model_id} missing output_price"
            assert isinstance(pricing.context_window, int), f"{model_id} missing context_window"
            assert isinstance(pricing.provider, str), f"{model_id} missing provider"
            assert pricing.input_price >= 0, f"{model_id} has negative input_price"
            assert pricing.output_price >= 0, f"{model_id} has negative output_price"
