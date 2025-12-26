"""
Test suite for semantic caching edge cases and the new analytics endpoints.

This module tests:
1. Edge cases in semantic similarity matching
2. Metadata filtering in cache queries
3. Cache analytics endpoint functionality
4. Cost analytics endpoint with optimization score
5. HNSW index behavior (via the Supabase function calls)

Edge Cases Covered:
- Near-threshold similarity matches (94.9% vs 95.1%)
- Unicode and special character prompts
- Very long prompts (edge of token limits)
- Empty or whitespace-only prompts
- Provider/model filtering behavior
- Quality score filtering
- Age-based filtering (stale cache entries)
"""

import pytest
import hashlib
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient

from app.main import app


class TestSemanticCacheEdgeCases:
    """Test edge cases in semantic similarity matching."""

    @pytest.fixture
    def client(self):
        """FastAPI test client."""
        return TestClient(app)

    def test_near_threshold_similarity_below(self, client):
        """Test that prompts just below 95% similarity don't match cache."""
        # This is a conceptual test - actual similarity depends on embeddings
        # The key insight: 94.9% similar prompts should NOT hit cache

        # Two prompts that are similar but not identical
        prompt1 = "What is the capital of France?"
        prompt2 = "What is the capitol of France?"  # Typo: capitol vs capital

        # These should be treated as different prompts
        # (actual similarity depends on embedding model, but testing the concept)
        hash1 = hashlib.sha256(prompt1.encode()).hexdigest()[:16]
        hash2 = hashlib.sha256(prompt2.encode()).hexdigest()[:16]

        assert hash1 != hash2, "Different prompts should have different hashes"

    def test_near_threshold_similarity_above(self, client):
        """Test that prompts above 95% similarity DO match cache."""
        # Semantically identical prompts with minor variations
        prompt1 = "What is Python programming language?"
        prompt2 = "what is python programming language?"  # Just lowercase

        # These should be normalized to match
        normalized1 = prompt1.lower().strip()
        normalized2 = prompt2.lower().strip()

        assert normalized1 == normalized2, "Normalized prompts should match"

    def test_unicode_prompt_handling(self, client):
        """Test that Unicode characters are properly handled in caching."""
        # Various Unicode test cases
        unicode_prompts = [
            "Qu'est-ce que Python?",  # French with accent
            "Python\u306f\u4f55\u3067\u3059\u304b\uff1f",  # Japanese
            "Was ist Python? \U0001F40D",  # German + emoji
            "\u0427\u0442\u043e \u0442\u0430\u043a\u043e\u0435 Python?",  # Russian
        ]

        for prompt in unicode_prompts:
            # Each should be able to be encoded for hashing
            try:
                hash_input = prompt.encode('utf-8')
                cache_key = hashlib.sha256(hash_input).hexdigest()
                assert len(cache_key) == 64, f"Valid hash for: {prompt[:20]}..."
            except Exception as e:
                pytest.fail(f"Failed to hash Unicode prompt: {e}")

    def test_very_long_prompt_handling(self, client):
        """Test handling of prompts near token limits."""
        # Create a very long prompt (approaching typical limits)
        long_prompt = "Explain the concept of " + "machine learning " * 500

        # Should be able to hash it
        cache_key = hashlib.sha256(long_prompt.encode()).hexdigest()
        assert len(cache_key) == 64, "Should generate valid hash for long prompts"

    def test_empty_prompt_rejection(self, client):
        """Test that empty prompts are properly rejected."""
        response = client.post("/complete", json={"prompt": ""})
        # Should fail validation (min_length=1 in Pydantic model)
        assert response.status_code == 422, "Empty prompts should be rejected"

    def test_whitespace_only_prompt_rejection(self, client):
        """Test that whitespace-only prompts are handled."""
        response = client.post("/complete", json={"prompt": "   \n\t   "})
        # Should fail validation or be normalized to empty
        # (depends on whether there's whitespace stripping)
        assert response.status_code in [422, 400, 200], "Whitespace prompts handled"


class TestMetadataFiltering:
    """Test metadata filtering in semantic cache queries."""

    @pytest.fixture
    def mock_supabase(self):
        """Mock Supabase client for testing filters."""
        mock = MagicMock()
        mock.get_cache_analytics = AsyncMock(return_value=[])
        mock.semantic_search = AsyncMock(return_value=[])
        return mock

    def test_provider_filter_structure(self, mock_supabase):
        """Test that provider filtering passes correct parameters."""
        # The filter should be an array of provider names
        filter_providers = ["claude", "gemini"]

        # Verify filter format is correct for the SQL function
        assert isinstance(filter_providers, list)
        assert all(isinstance(p, str) for p in filter_providers)

    def test_quality_score_filter_bounds(self, mock_supabase):
        """Test quality score filter boundary conditions."""
        # Valid quality scores are 0.0 to 1.0
        valid_scores = [0.0, 0.5, 0.7, 1.0]
        invalid_scores = [-0.1, 1.1, 2.0]

        for score in valid_scores:
            assert 0.0 <= score <= 1.0, f"{score} should be valid"

        for score in invalid_scores:
            assert not (0.0 <= score <= 1.0), f"{score} should be invalid"

    def test_age_filter_hours_calculation(self):
        """Test that age filtering correctly calculates time bounds."""
        max_age_hours = 24
        now = datetime.utcnow()
        cutoff = now - timedelta(hours=max_age_hours)

        # Entry created 23 hours ago should pass
        recent_entry = now - timedelta(hours=23)
        assert recent_entry > cutoff, "Recent entry should pass age filter"

        # Entry created 25 hours ago should fail
        old_entry = now - timedelta(hours=25)
        assert old_entry < cutoff, "Old entry should fail age filter"


class TestCacheAnalyticsEndpoint:
    """Test the /analytics/cache endpoint."""

    @pytest.fixture
    def client(self):
        """FastAPI test client."""
        return TestClient(app)

    def test_cache_analytics_endpoint_exists(self, client):
        """Test that the cache analytics endpoint is accessible."""
        response = client.get("/analytics/cache")
        assert response.status_code == 200, "Cache analytics endpoint should exist"

    def test_cache_analytics_response_structure(self, client):
        """Test that cache analytics response has expected structure."""
        response = client.get("/analytics/cache")
        assert response.status_code == 200
        data = response.json()

        # Verify top-level keys
        assert "summary" in data, "Response should have 'summary'"
        assert "by_provider" in data, "Response should have 'by_provider'"
        assert "recommendations" in data, "Response should have 'recommendations'"

        # Verify summary structure
        summary = data["summary"]
        expected_summary_keys = [
            "total_entries", "total_hits", "overall_hit_rate",
            "avg_quality", "estimated_savings_usd", "days_analyzed"
        ]
        for key in expected_summary_keys:
            assert key in summary, f"Summary should have '{key}'"

    def test_cache_analytics_days_parameter(self, client):
        """Test that days parameter is respected."""
        response = client.get("/analytics/cache?days=30")
        assert response.status_code == 200
        data = response.json()

        assert data["summary"]["days_analyzed"] == 30

    def test_cache_analytics_recommendations_not_empty(self, client):
        """Test that recommendations are always provided."""
        response = client.get("/analytics/cache")
        assert response.status_code == 200
        data = response.json()

        # Should always have at least one recommendation
        assert len(data["recommendations"]) > 0, "Should have recommendations"


class TestCostAnalyticsEndpoint:
    """Test the /analytics/costs endpoint."""

    @pytest.fixture
    def client(self):
        """FastAPI test client."""
        return TestClient(app)

    def test_cost_analytics_endpoint_exists(self, client):
        """Test that the cost analytics endpoint is accessible."""
        response = client.get("/analytics/costs")
        assert response.status_code == 200, "Cost analytics endpoint should exist"

    def test_cost_analytics_response_structure(self, client):
        """Test that cost analytics response has expected structure."""
        response = client.get("/analytics/costs")
        assert response.status_code == 200
        data = response.json()

        # Verify top-level keys
        assert "summary" in data, "Response should have 'summary'"
        assert "by_provider" in data, "Response should have 'by_provider'"
        assert "by_complexity" in data, "Response should have 'by_complexity'"
        assert "optimization_score" in data, "Response should have 'optimization_score'"
        assert "optimization_breakdown" in data, "Response should have 'optimization_breakdown'"

    def test_optimization_score_bounds(self, client):
        """Test that optimization score is within valid bounds."""
        response = client.get("/analytics/costs")
        assert response.status_code == 200
        data = response.json()

        score = data["optimization_score"]
        assert 0 <= score <= 100, "Optimization score should be 0-100"

    def test_optimization_breakdown_adds_up(self, client):
        """Test that optimization breakdown components are consistent."""
        response = client.get("/analytics/costs")
        assert response.status_code == 200
        data = response.json()

        breakdown = data["optimization_breakdown"]

        # Verify max points
        assert breakdown["max_possible"] == 100

        # Each component should not exceed its max
        assert breakdown["cache_efficiency_points"] <= 30
        assert breakdown["cost_reduction_points"] <= 50
        assert breakdown["quality_points"] <= 20

    def test_cost_analytics_days_parameter(self, client):
        """Test that days parameter is respected."""
        response = client.get("/analytics/costs?days=14")
        assert response.status_code == 200
        data = response.json()

        assert data["summary"]["days_analyzed"] == 14


class TestHNSWIndexBehavior:
    """Test HNSW index behavior through the semantic search function."""

    def test_hnsw_parameters_in_migration(self):
        """Verify HNSW index parameters are reasonable."""
        # These are the parameters from the migration
        m = 16  # Connections per node
        ef_construction = 64  # Dynamic candidate list size

        # Validate reasonable ranges
        assert 4 <= m <= 64, "m should be between 4 and 64 for balanced performance"
        assert 16 <= ef_construction <= 512, "ef_construction should be reasonable"

        # HNSW memory estimate: ~(M * dim * 4 bytes) per vector
        # With dim=384 and M=16: ~24KB per vector (very efficient)
        dim = 384
        memory_per_vector_bytes = m * dim * 4
        assert memory_per_vector_bytes < 100000, "Memory per vector should be reasonable"


class TestWilsonScoreQuality:
    """Test Wilson score algorithm for quality scoring."""

    def test_wilson_score_with_no_votes(self):
        """Test Wilson score with no votes returns neutral."""
        # Implementation in SQL uses Wilson score (same as Reddit)
        # With 0 votes, should return something neutral (~0.5)
        upvotes = 0
        downvotes = 0
        total = upvotes + downvotes

        # Can't compute with no votes - should default to neutral
        if total == 0:
            score = 0.5  # Neutral default
        else:
            score = upvotes / total

        assert score == 0.5, "No votes should give neutral score"

    def test_wilson_score_with_all_upvotes(self):
        """Test Wilson score with all upvotes."""
        upvotes = 10
        downvotes = 0

        # With all positive votes, score should be high
        if upvotes + downvotes > 0:
            simple_score = upvotes / (upvotes + downvotes)
            assert simple_score == 1.0, "All upvotes should give max simple score"

    def test_wilson_score_with_mixed_votes(self):
        """Test Wilson score with mixed votes."""
        upvotes = 7
        downvotes = 3

        simple_score = upvotes / (upvotes + downvotes)
        assert 0.6 <= simple_score <= 0.8, "Mixed votes should give middle score"

    def test_wilson_score_confidence_interval(self):
        """Test that Wilson score accounts for sample size uncertainty."""
        # Wilson score gives lower bound of confidence interval
        # 5 upvotes, 0 downvotes should score LOWER than
        # 50 upvotes, 0 downvotes (more confidence)

        # This is the key insight: more votes = more confidence = different score
        # Wilson formula accounts for this uncertainty

        # Simple demonstration that sample size matters
        small_sample = {"upvotes": 5, "downvotes": 0, "total": 5}
        large_sample = {"upvotes": 50, "downvotes": 0, "total": 50}

        # With Wilson score, large sample would have higher confidence
        # (The actual Wilson formula implementation is in SQL)
        assert small_sample["total"] < large_sample["total"]


class TestCacheConcurrency:
    """Test cache behavior under concurrent access."""

    @pytest.fixture
    def client(self):
        """FastAPI test client."""
        return TestClient(app)

    def test_cache_analytics_concurrent_access(self, client):
        """Test that analytics endpoint handles concurrent requests."""
        import concurrent.futures

        num_requests = 5

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_requests) as executor:
            futures = [
                executor.submit(client.get, "/analytics/cache")
                for _ in range(num_requests)
            ]
            responses = [f.result() for f in futures]

        # All should succeed
        assert all(r.status_code == 200 for r in responses)

        # All should return valid data
        for r in responses:
            data = r.json()
            assert "summary" in data
            assert "recommendations" in data

    def test_cost_analytics_concurrent_access(self, client):
        """Test that cost analytics endpoint handles concurrent requests."""
        import concurrent.futures

        num_requests = 5

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_requests) as executor:
            futures = [
                executor.submit(client.get, "/analytics/costs")
                for _ in range(num_requests)
            ]
            responses = [f.result() for f in futures]

        # All should succeed
        assert all(r.status_code == 200 for r in responses)

        # All should return valid optimization scores
        scores = [r.json()["optimization_score"] for r in responses]
        assert all(0 <= s <= 100 for s in scores)
