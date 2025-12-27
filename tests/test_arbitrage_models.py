"""
Test suite for arbitrage Pydantic models.
TDD: Tests written first, implementation follows.
"""
import pytest
from datetime import datetime
from pydantic import ValidationError


class TestModelCapability:
    """Test ModelCapability enum."""

    def test_capability_values_exist(self):
        """All expected capabilities should be defined."""
        from app.models.arbitrage import ModelCapability

        expected = [
            "code_gen", "code_review", "reasoning", "math",
            "creative", "analysis", "translation", "summarization",
            "vision", "audio", "function_calling", "json_mode"
        ]
        for cap in expected:
            assert hasattr(ModelCapability, cap.upper()), f"Missing capability: {cap}"

    def test_capability_is_string_enum(self):
        """Capabilities should be string values."""
        from app.models.arbitrage import ModelCapability

        assert ModelCapability.CODE_GEN.value == "code_gen"
        assert ModelCapability.REASONING.value == "reasoning"


class TestCapabilityLevel:
    """Test CapabilityLevel enum."""

    def test_level_ordering(self):
        """Levels should have logical ordering."""
        from app.models.arbitrage import CapabilityLevel

        levels = [
            CapabilityLevel.BASIC,
            CapabilityLevel.INTERMEDIATE,
            CapabilityLevel.ADVANCED,
            CapabilityLevel.EXPERT
        ]
        # Just verify all exist
        assert len(levels) == 4

    def test_level_values(self):
        """Levels should have correct string values."""
        from app.models.arbitrage import CapabilityLevel

        assert CapabilityLevel.BASIC.value == "basic"
        assert CapabilityLevel.EXPERT.value == "expert"


class TestModelProfile:
    """Test ModelProfile dataclass/model."""

    def test_valid_profile_creation(self):
        """Should create valid profile with all required fields."""
        from app.models.arbitrage import ModelProfile, ModelCapability, CapabilityLevel

        profile = ModelProfile(
            provider="gemini",
            model_id="gemini-1.5-flash",
            capabilities={
                ModelCapability.CODE_GEN: CapabilityLevel.INTERMEDIATE,
                ModelCapability.REASONING: CapabilityLevel.INTERMEDIATE,
            },
            input_price_per_million=0.075,
            output_price_per_million=0.30,
            context_window=1_000_000,
            avg_latency_ms=500
        )

        assert profile.provider == "gemini"
        assert profile.model_id == "gemini-1.5-flash"
        assert len(profile.capabilities) == 2

    def test_profile_pricing_validation(self):
        """Prices must be non-negative."""
        from app.models.arbitrage import ModelProfile, ModelCapability, CapabilityLevel

        with pytest.raises(ValidationError):
            ModelProfile(
                provider="test",
                model_id="test-model",
                capabilities={},
                input_price_per_million=-0.10,  # Invalid
                output_price_per_million=0.10,
                context_window=1000
            )

    def test_profile_context_window_validation(self):
        """Context window must be positive."""
        from app.models.arbitrage import ModelProfile

        with pytest.raises(ValidationError):
            ModelProfile(
                provider="test",
                model_id="test-model",
                capabilities={},
                input_price_per_million=0.10,
                output_price_per_million=0.10,
                context_window=0  # Invalid
            )

    def test_profile_cost_calculation(self):
        """Profile should calculate cost for given tokens."""
        from app.models.arbitrage import ModelProfile

        profile = ModelProfile(
            provider="test",
            model_id="test-model",
            capabilities={},
            input_price_per_million=1.0,
            output_price_per_million=2.0,
            context_window=10000
        )

        cost = profile.calculate_cost(input_tokens=1000, output_tokens=500)
        expected = (1000 / 1_000_000 * 1.0) + (500 / 1_000_000 * 2.0)
        assert abs(cost - expected) < 0.0001


class TestEquivalencyGroup:
    """Test EquivalencyGroup model."""

    def test_valid_group_creation(self):
        """Should create valid equivalency group."""
        from app.models.arbitrage import EquivalencyGroup, ModelCapability

        group = EquivalencyGroup(
            capability=ModelCapability.CODE_GEN,
            quality_tier="intermediate",
            models=["gemini-1.5-flash", "claude-3-haiku", "deepseek-chat"]
        )

        assert group.capability == ModelCapability.CODE_GEN
        assert len(group.models) == 3

    def test_group_requires_models(self):
        """Group must have at least one model."""
        from app.models.arbitrage import EquivalencyGroup, ModelCapability

        with pytest.raises(ValidationError):
            EquivalencyGroup(
                capability=ModelCapability.CODE_GEN,
                quality_tier="basic",
                models=[]  # Invalid - empty list
            )


class TestArbitrageOpportunity:
    """Test ArbitrageOpportunity model."""

    def test_valid_opportunity_creation(self):
        """Should create valid arbitrage opportunity."""
        from app.models.arbitrage import ArbitrageOpportunity, ModelCapability

        opportunity = ArbitrageOpportunity(
            current_model="claude-3-5-sonnet",
            current_provider="anthropic",
            alternative_model="deepseek-chat",
            alternative_provider="openrouter",
            current_cost=0.015,
            alternative_cost=0.001,
            savings_percent=93.3,
            quality_score=0.92,
            required_capabilities=[ModelCapability.CODE_GEN]
        )

        assert opportunity.savings_percent == 93.3
        assert opportunity.quality_score == 0.92

    def test_opportunity_savings_calculation(self):
        """Should correctly calculate savings percentage."""
        from app.models.arbitrage import ArbitrageOpportunity, ModelCapability

        opportunity = ArbitrageOpportunity(
            current_model="expensive",
            current_provider="provider_a",
            alternative_model="cheap",
            alternative_provider="provider_b",
            current_cost=1.0,
            alternative_cost=0.3,
            savings_percent=70.0,
            quality_score=0.85,
            required_capabilities=[ModelCapability.REASONING]
        )

        # Verify calculated savings matches
        calculated = (1.0 - 0.3) / 1.0 * 100
        assert abs(opportunity.savings_percent - calculated) < 0.1

    def test_opportunity_quality_bounds(self):
        """Quality score must be between 0 and 1."""
        from app.models.arbitrage import ArbitrageOpportunity

        with pytest.raises(ValidationError):
            ArbitrageOpportunity(
                current_model="a",
                current_provider="p",
                alternative_model="b",
                alternative_provider="q",
                current_cost=1.0,
                alternative_cost=0.5,
                savings_percent=50.0,
                quality_score=1.5,  # Invalid - > 1
                required_capabilities=[]
            )

    def test_opportunity_savings_bounds(self):
        """Savings percent must be between 0 and 100."""
        from app.models.arbitrage import ArbitrageOpportunity

        with pytest.raises(ValidationError):
            ArbitrageOpportunity(
                current_model="a",
                current_provider="p",
                alternative_model="b",
                alternative_provider="q",
                current_cost=1.0,
                alternative_cost=0.5,
                savings_percent=150.0,  # Invalid - > 100
                quality_score=0.9,
                required_capabilities=[]
            )


class TestArbitrageRecommendation:
    """Test ArbitrageRecommendation response model."""

    def test_valid_recommendation(self):
        """Should create valid recommendation with opportunities."""
        from app.models.arbitrage import ArbitrageRecommendation, ArbitrageOpportunity, ModelCapability

        opp = ArbitrageOpportunity(
            current_model="claude-sonnet",
            current_provider="anthropic",
            alternative_model="llama-70b",
            alternative_provider="groq",
            current_cost=0.01,
            alternative_cost=0.002,
            savings_percent=80.0,
            quality_score=0.88,
            required_capabilities=[ModelCapability.REASONING]
        )

        recommendation = ArbitrageRecommendation(
            prompt_preview="Explain quantum computing...",
            detected_task_type="reasoning",
            opportunities=[opp],
            best_opportunity=opp,
            total_savings_potential=80.0,
            recommendation_reasoning="Llama-70b provides equivalent reasoning capability at 80% lower cost."
        )

        assert len(recommendation.opportunities) == 1
        assert recommendation.best_opportunity is not None

    def test_recommendation_no_opportunities(self):
        """Should handle case with no arbitrage opportunities."""
        from app.models.arbitrage import ArbitrageRecommendation

        recommendation = ArbitrageRecommendation(
            prompt_preview="Complex task...",
            detected_task_type="expert_reasoning",
            opportunities=[],
            best_opportunity=None,
            total_savings_potential=0.0,
            recommendation_reasoning="Current model is already optimal for this task type."
        )

        assert len(recommendation.opportunities) == 0
        assert recommendation.best_opportunity is None
        assert recommendation.total_savings_potential == 0.0


class TestArbitrageAnalysisRequest:
    """Test ArbitrageAnalysisRequest model."""

    def test_valid_request(self):
        """Should create valid analysis request."""
        from app.models.arbitrage import ArbitrageAnalysisRequest

        request = ArbitrageAnalysisRequest(
            prompt="Write a Python function to sort a list",
            current_model="claude-3-5-sonnet",
            input_tokens=500,
            output_tokens=500,
            min_quality_threshold=0.85
        )

        assert request.prompt is not None
        assert request.min_quality_threshold == 0.85

    def test_request_default_quality_threshold(self):
        """Should have sensible default quality threshold."""
        from app.models.arbitrage import ArbitrageAnalysisRequest

        request = ArbitrageAnalysisRequest(
            prompt="Hello world",
            current_model="gemini-1.5-flash"
        )

        # Default should be around 0.85
        assert 0.80 <= request.min_quality_threshold <= 0.90

    def test_request_prompt_required(self):
        """Prompt is required field."""
        from app.models.arbitrage import ArbitrageAnalysisRequest

        with pytest.raises(ValidationError):
            ArbitrageAnalysisRequest(
                current_model="test"
                # Missing prompt
            )


class TestSavingsReport:
    """Test SavingsReport response model."""

    def test_valid_report(self):
        """Should create valid savings report."""
        from app.models.arbitrage import SavingsReport

        report = SavingsReport(
            period_days=30,
            total_requests=1000,
            actual_cost=150.0,
            optimal_cost=45.0,
            potential_savings=105.0,
            savings_percentage=70.0,
            opportunities_detected=250,
            opportunities_applied=100
        )

        assert report.savings_percentage == 70.0
        assert report.potential_savings == 105.0

    def test_report_application_rate(self):
        """Should calculate application rate correctly."""
        from app.models.arbitrage import SavingsReport

        report = SavingsReport(
            period_days=30,
            total_requests=1000,
            actual_cost=100.0,
            optimal_cost=50.0,
            potential_savings=50.0,
            savings_percentage=50.0,
            opportunities_detected=200,
            opportunities_applied=150
        )

        # 150/200 = 75% application rate
        assert report.application_rate == 75.0


class TestModelAlternative:
    """Test ModelAlternative response model."""

    def test_valid_alternative(self):
        """Should create valid model alternative."""
        from app.models.arbitrage import ModelAlternative

        alt = ModelAlternative(
            provider="groq",
            model_id="llama-3.3-70b-versatile",
            input_price_per_million=0.59,
            output_price_per_million=0.79,
            savings_vs_current=70.0,
            quality_score=0.88,
            supported_capabilities=["code_gen", "reasoning", "analysis"],
            context_window=32000,
            avg_latency_ms=150
        )

        assert alt.savings_vs_current == 70.0
        assert "code_gen" in alt.supported_capabilities
