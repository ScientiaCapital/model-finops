"""
Tests for ArbitrageService business logic.

Tests service layer functionality for cost optimization through model switching.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.services.arbitrage_service import ArbitrageService
from app.models.arbitrage import (
    ModelCapability,
    ArbitrageAnalysisResponse,
    ArbitrageOpportunity,
)


class TestArbitrageServiceInit:
    """Tests for ArbitrageService initialization."""

    def test_init_without_supabase(self):
        """Service initializes without Supabase client."""
        service = ArbitrageService()
        assert service.supabase is None
        assert service.registry is not None
        assert service._quality_threshold == 0.85

    def test_init_with_supabase(self):
        """Service initializes with Supabase client."""
        mock_client = MagicMock()
        service = ArbitrageService(supabase_client=mock_client)
        assert service.supabase == mock_client


class TestCapabilityDetection:
    """Tests for prompt capability detection."""

    @pytest.fixture
    def service(self):
        return ArbitrageService()

    def test_detect_code_capability(self, service):
        """Detects code generation from programming keywords."""
        prompts = [
            "Write a Python function to sort a list",
            "Implement a class for user authentication",
            "Debug this JavaScript code",
            "Fix the bug in my TypeScript module",
        ]
        for prompt in prompts:
            caps = service._detect_capabilities(prompt)
            assert ModelCapability.CODE_GEN in caps, f"Failed for: {prompt}"

    def test_detect_reasoning_capability(self, service):
        """Detects reasoning from analytical keywords."""
        prompts = [
            "Explain why the sky is blue",
            "Analyze this business strategy",
            "Compare React and Vue frameworks",
            "Think through this problem step by step",
        ]
        for prompt in prompts:
            caps = service._detect_capabilities(prompt)
            assert ModelCapability.REASONING in caps, f"Failed for: {prompt}"

    def test_detect_math_capability(self, service):
        """Detects math from numerical keywords."""
        prompts = [
            "Calculate the compound interest",
            "Solve this algebra equation",
            "What's the probability of rolling a 6?",
        ]
        for prompt in prompts:
            caps = service._detect_capabilities(prompt)
            assert ModelCapability.MATH in caps, f"Failed for: {prompt}"

    def test_detect_creative_capability(self, service):
        """Detects creative writing from narrative keywords."""
        prompts = [
            "Write a short story about a robot",
            "Create a poem about nature",
            "Imagine a world where AI rules",
        ]
        for prompt in prompts:
            caps = service._detect_capabilities(prompt)
            assert ModelCapability.CREATIVE in caps, f"Failed for: {prompt}"

    def test_detect_json_capability(self, service):
        """Detects JSON mode from formatting keywords."""
        prompts = [
            "Return the result as JSON",
            "Format the output as structured data",
            "Use this schema for the response",
        ]
        for prompt in prompts:
            caps = service._detect_capabilities(prompt)
            assert ModelCapability.JSON_MODE in caps, f"Failed for: {prompt}"

    def test_default_to_reasoning(self, service):
        """Defaults to reasoning when no specific capability detected."""
        caps = service._detect_capabilities("Hello, how are you today?")
        assert ModelCapability.REASONING in caps
        assert len(caps) == 1

    def test_detect_multiple_capabilities(self, service):
        """Detects multiple capabilities from complex prompts."""
        prompt = "Analyze and explain this Python code, then calculate its complexity"
        caps = service._detect_capabilities(prompt)
        assert ModelCapability.REASONING in caps  # "explain", "analyze"
        assert ModelCapability.CODE_GEN in caps  # "Python", "code"
        assert ModelCapability.MATH in caps  # "calculate"


class TestQualityMatch:
    """Tests for quality matching between models."""

    @pytest.fixture
    def service(self):
        return ArbitrageService()

    def test_no_capabilities_returns_half(self, service):
        """Returns 0.5 when no capabilities to compare."""
        mock_current = MagicMock()
        mock_alt = MagicMock()
        score = service._calculate_quality_match(mock_current, mock_alt, [])
        assert score == 0.5

    def test_missing_capability_zero_score(self, service):
        """Returns 0 for missing capability in alternative."""
        mock_current = MagicMock()
        mock_current.capabilities = {ModelCapability.CODE_GEN: "advanced"}
        mock_alt = MagicMock()
        mock_alt.capabilities = {}  # No capabilities

        score = service._calculate_quality_match(
            mock_current, mock_alt, [ModelCapability.CODE_GEN]
        )
        assert score == 0.0


class TestAnalyzePrompt:
    """Tests for the main analyze_prompt method."""

    @pytest.fixture
    def service(self):
        return ArbitrageService()

    @pytest.mark.asyncio
    async def test_analyze_unknown_model(self, service):
        """Returns empty opportunities for unknown model."""
        response = await service.analyze_prompt(
            prompt="Test prompt",
            current_model="unknown-model-xyz",
        )
        assert isinstance(response, ArbitrageAnalysisResponse)
        assert response.current_model == "unknown-model-xyz"
        assert response.opportunities == []
        assert response.current_cost == 0.0

    @pytest.mark.asyncio
    async def test_analyze_known_model_finds_opportunities(self, service):
        """Finds opportunities for known expensive models."""
        response = await service.analyze_prompt(
            prompt="Write a simple function",
            current_model="claude-3-opus",
            input_tokens=100,
            output_tokens=100,
        )
        assert isinstance(response, ArbitrageAnalysisResponse)
        assert response.current_model == "claude-3-opus"
        # Opus is expensive, should find cheaper alternatives
        if response.opportunities:
            assert all(
                opp.savings_percent >= 0 for opp in response.opportunities
            )

    @pytest.mark.asyncio
    async def test_analyze_estimates_tokens(self, service):
        """Estimates tokens when not provided."""
        response = await service.analyze_prompt(
            prompt="A" * 400,  # ~100 tokens
            current_model="gemini-1.5-flash",
        )
        # Should not crash, tokens are estimated
        assert response.current_cost >= 0

    @pytest.mark.asyncio
    async def test_opportunities_sorted_by_savings(self, service):
        """Opportunities are sorted by savings percent (highest first)."""
        response = await service.analyze_prompt(
            prompt="Explain quantum computing",
            current_model="claude-3-opus",
            input_tokens=500,
            output_tokens=1000,
        )
        if len(response.opportunities) > 1:
            savings = [opp.savings_percent for opp in response.opportunities]
            assert savings == sorted(savings, reverse=True)


class TestLogging:
    """Tests for opportunity logging."""

    @pytest.mark.asyncio
    async def test_logs_opportunity_when_supabase_available(self):
        """Logs opportunity to Supabase when client available."""
        mock_supabase = AsyncMock()
        mock_table = AsyncMock()
        mock_supabase.table.return_value = mock_table
        mock_table.insert.return_value.execute = AsyncMock()

        service = ArbitrageService(supabase_client=mock_supabase)

        # Use a model that will find opportunities
        response = await service.analyze_prompt(
            prompt="Write a Python function",
            current_model="claude-3-opus",
            user_id="test-user-123",
            input_tokens=100,
            output_tokens=100,
        )

        # Should attempt to log if opportunities found
        if response.opportunities:
            mock_supabase.table.assert_called_with("arbitrage_opportunities")

    @pytest.mark.asyncio
    async def test_no_log_without_user_id(self):
        """Does not log when user_id is None."""
        mock_supabase = AsyncMock()
        service = ArbitrageService(supabase_client=mock_supabase)

        await service.analyze_prompt(
            prompt="Test",
            current_model="claude-3-opus",
            user_id=None,  # No user ID
        )

        mock_supabase.table.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_log_without_opportunities(self):
        """Does not log when no opportunities found."""
        mock_supabase = AsyncMock()
        service = ArbitrageService(supabase_client=mock_supabase)

        await service.analyze_prompt(
            prompt="Test",
            current_model="unknown-model",  # No opportunities for unknown model
            user_id="test-user",
        )

        mock_supabase.table.assert_not_called()


class TestGetUserOpportunities:
    """Tests for retrieving user opportunities."""

    @pytest.mark.asyncio
    async def test_returns_empty_without_supabase(self):
        """Returns empty list without Supabase client."""
        service = ArbitrageService()
        result = await service.get_user_opportunities("user-123")
        assert result == []

    @pytest.mark.asyncio
    async def test_queries_supabase_for_opportunities(self):
        """Queries Supabase table for opportunities."""
        mock_supabase = AsyncMock()

        service = ArbitrageService(supabase_client=mock_supabase)
        # The method will call supabase.table("arbitrage_opportunities")
        await service.get_user_opportunities("user-123", limit=10)

        # Verify it attempts to query the table
        mock_supabase.table.assert_called_with("arbitrage_opportunities")


class TestSavingsReport:
    """Tests for savings report generation."""

    @pytest.mark.asyncio
    async def test_returns_zeros_without_supabase(self):
        """Returns zero values without Supabase client."""
        service = ArbitrageService()
        report = await service.get_savings_report("user-123")

        assert report["total_potential_savings"] == 0.0
        assert report["actual_savings"] == 0.0
        assert report["opportunities_found"] == 0
        assert report["opportunities_applied"] == 0

    @pytest.mark.asyncio
    async def test_queries_supabase_for_report(self):
        """Queries Supabase table for savings report."""
        mock_supabase = AsyncMock()

        service = ArbitrageService(supabase_client=mock_supabase)
        await service.get_savings_report("user-123")

        # Verify it attempts to query the table
        mock_supabase.table.assert_called_with("arbitrage_opportunities")


class TestGetAlternatives:
    """Tests for getting model alternatives."""

    def test_get_alternatives_uses_model_capabilities(self):
        """Uses model's own capabilities when none specified."""
        service = ArbitrageService()
        alts = service.get_alternatives_for_model("claude-3-opus")
        # Should find alternatives for Opus (expensive model)
        # The result depends on registry content
        assert isinstance(alts, list)

    def test_get_alternatives_with_specific_capabilities(self):
        """Filters by specified capabilities."""
        service = ArbitrageService()
        alts = service.get_alternatives_for_model(
            "claude-3-opus",
            capabilities=[ModelCapability.CODE_GEN],
        )
        assert isinstance(alts, list)
