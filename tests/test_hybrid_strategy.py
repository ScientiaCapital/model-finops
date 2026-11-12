"""Tests for HybridStrategy."""

from unittest.mock import patch

import pytest

from app.routing.models import RoutingContext, RoutingDecision
from app.routing.strategy import HybridStrategy


@pytest.fixture
def hybrid_strategy(tmp_path):
    """Create HybridStrategy with test database."""
    db_path = tmp_path / "test.db"
    return HybridStrategy(db_path=str(db_path))


def test_high_confidence_learning_accepted(hybrid_strategy):
    """Test HIGH confidence from learning, complexity agrees -> use learning."""
    prompt = "Simple question"
    context = RoutingContext(prompt=prompt)

    # Mock learning strategy to return HIGH confidence
    with patch.object(hybrid_strategy.learning_strategy, "route") as mock_learning:
        mock_learning.return_value = RoutingDecision(
            provider="gemini",
            model="gemini-1.5-flash",
            confidence="high",
            strategy_used="learning",
            reasoning="High confidence from learning data",
            fallback_used=False,
            metadata={"pattern": "simple_query", "quality_score": 0.95},
        )

        decision = hybrid_strategy.route(prompt, context)

        # Should use learning decision with hybrid strategy
        assert decision.provider == "gemini"
        assert decision.model == "gemini-1.5-flash"
        assert decision.confidence == "high"
        assert decision.strategy_used == "hybrid"
        assert "complexity" in decision.metadata
        assert decision.metadata["validation"] == "validated"
        assert "validated by complexity" in decision.reasoning


def test_high_confidence_learning_validation_rejects_mismatch(hybrid_strategy):
    """High learning confidence but strong complexity disagreement: use complexity."""
    # Complex prompt triggers high complexity score (>0.7)
    prompt = (
        "Analyze and explain the comprehensive mathematical framework for quantum entanglement,\n"
        "    including detailed proofs, derivations, and computational examples spanning multiple "
        "domains..."
    )

    context = RoutingContext(prompt=prompt)

    # Mock learning to recommend Gemini (cheap/simple) with HIGH confidence
    # This is a MISMATCH - learning says simple, complexity says complex
    with patch.object(hybrid_strategy.learning_strategy, "route") as mock_learning:
        mock_learning.return_value = RoutingDecision(
            provider="gemini",
            model="gemini-1.5-flash",  # Simple tier
            confidence="high",
            strategy_used="learning",
            reasoning="High confidence: pattern seen 100+ times",
            fallback_used=False,
            metadata={"pattern": "technical_query", "quality_score": 0.92},
        )

        decision = hybrid_strategy.route(prompt, context)

        # Should REJECT learning because complexity strongly disagrees
        # Complex prompt should route to Claude Sonnet (complex tier)
        assert decision.provider != "gemini", "Should reject Gemini for complex prompt"
        assert decision.strategy_used == "hybrid"
        assert decision.metadata.get("learning_mismatch") is True
        assert decision.metadata.get("rejected_model") == "gemini-1.5-flash"
        # Verify complexity routing to complex tier
        assert "claude" in decision.provider.lower() or "sonnet" in decision.model.lower()


def test_high_confidence_learning_validation_accepts_match(hybrid_strategy):
    """Test HIGH confidence from learning with complexity AGREEMENT -> ACCEPT learning."""
    # Simple prompt triggers low complexity score (<0.3)
    prompt = "What is Python?"
    context = RoutingContext(prompt=prompt)

    # Mock learning to recommend Gemini with HIGH confidence
    # This is a MATCH - both learning and complexity agree on simple tier
    with patch.object(hybrid_strategy.learning_strategy, "route") as mock_learning:
        mock_learning.return_value = RoutingDecision(
            provider="gemini",
            model="gemini-1.5-flash",
            confidence="high",
            strategy_used="learning",
            reasoning="High confidence: simple query pattern",
            fallback_used=False,
            metadata={"pattern": "simple_query", "quality_score": 0.95},
        )

        decision = hybrid_strategy.route(prompt, context)

        # Should ACCEPT learning because complexity agrees (simple → Gemini)
        assert decision.provider == "gemini"
        assert decision.model == "gemini-1.5-flash"
        assert decision.confidence == "high"
        assert decision.strategy_used == "hybrid"
        assert decision.metadata["validation"] == "validated"
        assert "validated by complexity" in decision.reasoning
        assert (
            decision.metadata.get("learning_mismatch") is None
            or decision.metadata["learning_mismatch"] is False
        )


def test_low_confidence_experimental(hybrid_strategy):
    """Test LOW confidence from learning -> use learning with experimental flag."""
    prompt = "Some rare query pattern"
    context = RoutingContext(prompt=prompt)

    # Mock learning strategy to return LOW confidence
    with patch.object(hybrid_strategy.learning_strategy, "route") as mock_learning:
        mock_learning.return_value = RoutingDecision(
            provider="claude",
            model="claude-3-haiku-20240307",
            confidence="low",
            strategy_used="learning",
            reasoning="Low confidence: only 3 samples",
            fallback_used=False,
            metadata={"pattern": "rare_query", "quality_score": 0.75},
        )

        decision = hybrid_strategy.route(prompt, context)

        # Should use learning but mark as experimental
        assert decision.provider == "claude"
        assert decision.model == "claude-3-haiku-20240307"
        assert decision.confidence == "medium"  # Capped at medium
        assert decision.strategy_used == "hybrid"
        assert decision.metadata["validation"] == "experimental"
        assert decision.metadata["experimental"] is True
        assert "Experimental routing" in decision.reasoning


def test_no_learning_data_fallback(hybrid_strategy):
    """Test no learning data available -> fallback to ComplexityStrategy."""
    prompt = "What is Python?"
    context = RoutingContext(prompt=prompt)

    # Mock learning strategy to raise exception (simulating no data)
    with patch.object(hybrid_strategy.learning_strategy, "route") as mock_learning:
        mock_learning.side_effect = FileNotFoundError("No training data")

        decision = hybrid_strategy.route(prompt, context)

        # Should fallback to complexity strategy
        assert decision.strategy_used == "hybrid_fallback"
        assert "Fallback to complexity" in decision.reasoning
        assert "complexity" in decision.metadata
        # Simple prompt should route to Gemini via complexity
        assert decision.provider in ["gemini", "openrouter", "claude"]


def test_metadata_includes_both_strategies(hybrid_strategy):
    """Test metadata captures both learning and complexity scores."""
    prompt = "Moderate complexity query"
    context = RoutingContext(prompt=prompt)

    # Mock learning strategy to return MEDIUM confidence
    with patch.object(hybrid_strategy.learning_strategy, "route") as mock_learning:
        mock_learning.return_value = RoutingDecision(
            provider="claude",
            model="claude-3-haiku-20240307",
            confidence="medium",
            strategy_used="learning",
            reasoning="Medium confidence from learning",
            fallback_used=False,
            metadata={"pattern": "moderate_query", "quality_score": 0.82, "cost_estimate": 0.0001},
        )

        decision = hybrid_strategy.route(prompt, context)

        # Should have metadata from both strategies
        assert decision.strategy_used == "hybrid"
        assert "complexity" in decision.metadata
        assert "pattern" in decision.metadata
        assert "quality_score" in decision.metadata
        assert decision.metadata["validation"] == "experimental"
        assert decision.metadata["experimental"] is True


def test_hybrid_strategy_name(hybrid_strategy):
    """Test strategy returns correct name."""
    assert hybrid_strategy.get_name() == "hybrid"
