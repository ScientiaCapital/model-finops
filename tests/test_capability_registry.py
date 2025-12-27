"""
Test suite for CapabilityRegistry - model capabilities and pricing.
TDD: Tests written first, implementation follows.
"""
import pytest
from app.models.arbitrage import ModelCapability, CapabilityLevel


class TestCapabilityRegistry:
    """Test CapabilityRegistry core functionality."""

    def test_registry_initialization(self):
        """Registry should initialize with predefined models."""
        from app.arbitrage.capability_registry import CapabilityRegistry

        registry = CapabilityRegistry()
        # Should have multiple models registered
        assert len(registry.get_all_models()) >= 10

    def test_get_model_profile_known_model(self):
        """Should return profile for known models."""
        from app.arbitrage.capability_registry import CapabilityRegistry

        registry = CapabilityRegistry()
        profile = registry.get_model_profile("gemini-1.5-flash")

        assert profile is not None
        assert profile.provider == "gemini"
        assert profile.input_price_per_million > 0
        assert profile.context_window > 0

    def test_get_model_profile_unknown_model(self):
        """Should return None for unknown models."""
        from app.arbitrage.capability_registry import CapabilityRegistry

        registry = CapabilityRegistry()
        profile = registry.get_model_profile("nonexistent-model-xyz")

        assert profile is None

    def test_get_models_with_capability(self):
        """Should filter models by capability."""
        from app.arbitrage.capability_registry import CapabilityRegistry

        registry = CapabilityRegistry()
        models = registry.get_models_with_capability(ModelCapability.CODE_GEN)

        assert len(models) >= 3  # Multiple models support code generation
        for model in models:
            assert ModelCapability.CODE_GEN in model.capabilities

    def test_get_models_with_capability_and_level(self):
        """Should filter models by capability and minimum level."""
        from app.arbitrage.capability_registry import CapabilityRegistry

        registry = CapabilityRegistry()
        models = registry.get_models_with_capability(
            ModelCapability.REASONING,
            min_level=CapabilityLevel.ADVANCED
        )

        assert len(models) >= 1
        for model in models:
            level = model.capabilities.get(ModelCapability.REASONING)
            assert level in [CapabilityLevel.ADVANCED, CapabilityLevel.EXPERT]

    def test_get_cheaper_alternatives_exists(self):
        """Should find cheaper alternatives for expensive models."""
        from app.arbitrage.capability_registry import CapabilityRegistry

        registry = CapabilityRegistry()
        alternatives = registry.get_cheaper_alternatives(
            model_id="claude-3-5-sonnet-20241022",
            required_capabilities=[ModelCapability.CODE_GEN]
        )

        assert len(alternatives) >= 1
        # Claude Sonnet is expensive, should have cheaper alternatives
        for alt in alternatives:
            assert alt.input_price_per_million < 3.0  # Cheaper than Sonnet

    def test_get_cheaper_alternatives_sorted_by_price(self):
        """Alternatives should be sorted cheapest first."""
        from app.arbitrage.capability_registry import CapabilityRegistry

        registry = CapabilityRegistry()
        alternatives = registry.get_cheaper_alternatives(
            model_id="claude-3-5-sonnet-20241022",
            required_capabilities=[ModelCapability.CODE_GEN]
        )

        if len(alternatives) > 1:
            prices = [a.input_price_per_million for a in alternatives]
            assert prices == sorted(prices)  # Ascending order


class TestModelPricing:
    """Test pricing data accuracy."""

    def test_gemini_flash_pricing(self):
        """Gemini Flash should have correct pricing."""
        from app.arbitrage.capability_registry import CapabilityRegistry

        registry = CapabilityRegistry()
        profile = registry.get_model_profile("gemini-1.5-flash")

        assert profile is not None
        # Google's published pricing (approximately)
        assert 0.05 <= profile.input_price_per_million <= 0.15
        assert 0.20 <= profile.output_price_per_million <= 0.40

    def test_claude_sonnet_pricing(self):
        """Claude Sonnet should have correct pricing."""
        from app.arbitrage.capability_registry import CapabilityRegistry

        registry = CapabilityRegistry()
        profile = registry.get_model_profile("claude-3-5-sonnet-20241022")

        assert profile is not None
        # Anthropic's published pricing (approximately)
        assert 2.5 <= profile.input_price_per_million <= 4.0
        assert 10.0 <= profile.output_price_per_million <= 20.0

    def test_groq_llama_pricing(self):
        """Groq Llama models should have competitive pricing."""
        from app.arbitrage.capability_registry import CapabilityRegistry

        registry = CapabilityRegistry()
        profile = registry.get_model_profile("llama-3.3-70b-versatile")

        assert profile is not None
        # Groq's competitive pricing (should be low)
        assert profile.input_price_per_million < 1.0


class TestCapabilityLevelOrdering:
    """Test capability level comparisons."""

    def test_level_ordering_values(self):
        """Levels should have consistent ordering."""
        levels = [
            CapabilityLevel.BASIC,
            CapabilityLevel.INTERMEDIATE,
            CapabilityLevel.ADVANCED,
            CapabilityLevel.EXPERT
        ]
        # They're enums with string values, so we can't directly compare
        # but the registry should use this ordering internally
        assert levels[0].value == "basic"
        assert levels[-1].value == "expert"


class TestProviderCoverage:
    """Test that all providers have models registered."""

    def test_gemini_provider_models(self):
        """Gemini provider should have models."""
        from app.arbitrage.capability_registry import CapabilityRegistry

        registry = CapabilityRegistry()
        models = registry.get_models_by_provider("gemini")
        assert len(models) >= 1

    def test_anthropic_provider_models(self):
        """Anthropic provider should have models."""
        from app.arbitrage.capability_registry import CapabilityRegistry

        registry = CapabilityRegistry()
        models = registry.get_models_by_provider("anthropic")
        assert len(models) >= 2  # Haiku and Sonnet at minimum

    def test_groq_provider_models(self):
        """Groq provider should have models."""
        from app.arbitrage.capability_registry import CapabilityRegistry

        registry = CapabilityRegistry()
        models = registry.get_models_by_provider("groq")
        assert len(models) >= 1

    def test_openrouter_provider_models(self):
        """OpenRouter provider should have models."""
        from app.arbitrage.capability_registry import CapabilityRegistry

        registry = CapabilityRegistry()
        models = registry.get_models_by_provider("openrouter")
        assert len(models) >= 1

    def test_cerebras_provider_models(self):
        """Cerebras provider should have models."""
        from app.arbitrage.capability_registry import CapabilityRegistry

        registry = CapabilityRegistry()
        models = registry.get_models_by_provider("cerebras")
        assert len(models) >= 1


class TestCapabilityCoverage:
    """Test capability assignments across models."""

    def test_code_generation_coverage(self):
        """Multiple models should support code generation."""
        from app.arbitrage.capability_registry import CapabilityRegistry

        registry = CapabilityRegistry()
        models = registry.get_models_with_capability(ModelCapability.CODE_GEN)
        assert len(models) >= 5

    def test_reasoning_coverage(self):
        """Multiple models should support reasoning."""
        from app.arbitrage.capability_registry import CapabilityRegistry

        registry = CapabilityRegistry()
        models = registry.get_models_with_capability(ModelCapability.REASONING)
        assert len(models) >= 5

    def test_math_coverage(self):
        """Some models should support math."""
        from app.arbitrage.capability_registry import CapabilityRegistry

        registry = CapabilityRegistry()
        models = registry.get_models_with_capability(ModelCapability.MATH)
        assert len(models) >= 3


class TestCostCalculation:
    """Test cost calculation utilities."""

    def test_compare_costs(self):
        """Should correctly compare costs between models."""
        from app.arbitrage.capability_registry import CapabilityRegistry

        registry = CapabilityRegistry()

        # Compare Claude Sonnet vs Gemini Flash for same tokens
        sonnet = registry.get_model_profile("claude-3-5-sonnet-20241022")
        flash = registry.get_model_profile("gemini-1.5-flash")

        assert sonnet is not None
        assert flash is not None

        tokens = 1000
        sonnet_cost = sonnet.calculate_cost(tokens, tokens)
        flash_cost = flash.calculate_cost(tokens, tokens)

        # Gemini Flash should be significantly cheaper
        assert flash_cost < sonnet_cost
        savings = (sonnet_cost - flash_cost) / sonnet_cost * 100
        assert savings > 50  # At least 50% cheaper

    def test_get_cheapest_for_capability(self):
        """Should find cheapest model for a capability."""
        from app.arbitrage.capability_registry import CapabilityRegistry

        registry = CapabilityRegistry()
        cheapest = registry.get_cheapest_model(ModelCapability.CODE_GEN)

        assert cheapest is not None
        # Should be one of the cheap options
        assert cheapest.input_price_per_million < 1.0
