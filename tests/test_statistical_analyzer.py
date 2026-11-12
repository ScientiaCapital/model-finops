"""
Tests for Statistical Analyzer - A/B Test Significance Testing.

This test suite validates statistical analysis functionality:
- Chi-square tests for categorical outcomes (success/failure)
- T-tests for continuous metrics (latency, cost)
- Winner detection with confidence thresholds
- Minimum sample size validation
- Effect size calculations
"""

import pytest

from app.experiments.statistical_analyzer import StatisticalAnalyzer


class TestChiSquareTest:
    """Test chi-square significance testing for categorical outcomes."""

    def test_chi_square_significant_difference(self):
        """Detect statistically significant difference in success rates."""
        analyzer = StatisticalAnalyzer()

        # Control: 70% success rate (70/100)
        # Test: 85% success rate (85/100)
        # Expected: Significant difference
        result = analyzer.chi_square_test(
            control_successes=70, control_total=100, test_successes=85, test_total=100
        )

        assert result["significant"] is True
        assert result["p_value"] < 0.05
        assert "chi_square_statistic" in result
        assert result["control_rate"] == 0.70
        assert result["test_rate"] == 0.85

    def test_chi_square_no_difference(self):
        """Detect when no significant difference exists."""
        analyzer = StatisticalAnalyzer()

        # Control: 75% success (75/100)
        # Test: 77% success (77/100)
        # Expected: Not significant
        result = analyzer.chi_square_test(
            control_successes=75, control_total=100, test_successes=77, test_total=100
        )

        assert result["significant"] is False
        assert result["p_value"] >= 0.05

    def test_chi_square_insufficient_sample_size(self):
        """Reject test with too few samples."""
        analyzer = StatisticalAnalyzer()

        # Only 10 samples per group - too small
        with pytest.raises(ValueError, match="sample size"):
            analyzer.chi_square_test(
                control_successes=7, control_total=10, test_successes=9, test_total=10
            )

    def test_chi_square_zero_variance(self):
        """Handle edge case where all samples succeed."""
        analyzer = StatisticalAnalyzer()

        # Both groups 100% success
        result = analyzer.chi_square_test(
            control_successes=50, control_total=50, test_successes=50, test_total=50
        )

        assert result["significant"] is False
        assert result["p_value"] == 1.0  # Perfect equality


class TestTTest:
    """Test t-test for continuous metrics (latency, cost, quality)."""

    def test_ttest_significant_latency_improvement(self):
        """Detect significant latency improvement."""
        analyzer = StatisticalAnalyzer()

        # Control: avg=50ms
        # Test: avg=35ms (30% improvement)
        control_values = [50, 52, 48, 51, 49] * 10  # 50 samples
        test_values = [35, 37, 33, 36, 34] * 10  # 50 samples

        result = analyzer.ttest_independent(
            control_values=control_values, test_values=test_values, metric_name="latency_ms"
        )

        assert result["significant"] is True
        assert result["p_value"] < 0.05
        assert result["control_mean"] > result["test_mean"]  # Test is faster
        assert "effect_size" in result

    def test_ttest_no_cost_difference(self):
        """Detect when cost difference is not significant."""
        analyzer = StatisticalAnalyzer()

        # Control: avg=$0.001 with realistic variance
        # Test: avg=$0.00105 (5% difference, not significant with high variance)
        import random

        random.seed(42)  # Reproducible
        control_values = [0.001 + random.gauss(0, 0.0003) for _ in range(60)]
        test_values = [0.00105 + random.gauss(0, 0.0003) for _ in range(60)]

        result = analyzer.ttest_independent(
            control_values=control_values, test_values=test_values, metric_name="cost_usd"
        )

        assert result["significant"] is False
        assert result["p_value"] >= 0.05

    def test_ttest_insufficient_samples(self):
        """Reject t-test with too few samples."""
        analyzer = StatisticalAnalyzer()

        with pytest.raises(ValueError, match="sample size"):
            analyzer.ttest_independent(
                control_values=[1, 2, 3],  # Only 3 samples
                test_values=[4, 5, 6],
                metric_name="latency_ms",
            )

    def test_ttest_effect_size_calculation(self):
        """Verify Cohen's d effect size calculation."""
        analyzer = StatisticalAnalyzer()

        # Large effect: Control=100, Test=80 (20% improvement)
        control_values = [100] * 30
        test_values = [80] * 30

        result = analyzer.ttest_independent(
            control_values=control_values, test_values=test_values, metric_name="latency_ms"
        )

        assert result["effect_size"] > 0.8  # Large effect (Cohen's d)


class TestWinnerDetection:
    """Test automatic winner detection based on multiple metrics."""

    def test_detect_clear_winner(self):
        """Detect clear winner when test outperforms on all metrics."""
        analyzer = StatisticalAnalyzer()

        experiment_summary = {
            "control": {
                "count": 100,
                "avg_latency_ms": 50.0,
                "avg_cost_usd": 0.002,
                "avg_quality_score": 7.5,
            },
            "test": {
                "count": 100,
                "avg_latency_ms": 35.0,  # 30% faster
                "avg_cost_usd": 0.0015,  # 25% cheaper
                "avg_quality_score": 8.5,  # Higher quality
            },
        }

        result = analyzer.detect_winner(experiment_summary)

        assert result["winner"] == "test"
        assert result["confidence"] == "high"
        assert "latency" in result["winning_metrics"]
        assert "cost" in result["winning_metrics"]
        assert "quality" in result["winning_metrics"]

    def test_no_clear_winner_mixed_results(self):
        """No winner when metrics are mixed (tradeoffs)."""
        analyzer = StatisticalAnalyzer()

        experiment_summary = {
            "control": {
                "count": 100,
                "avg_latency_ms": 50.0,
                "avg_cost_usd": 0.001,  # Cheaper
                "avg_quality_score": 7.0,
            },
            "test": {
                "count": 100,
                "avg_latency_ms": 35.0,  # Faster
                "avg_cost_usd": 0.003,  # But more expensive
                "avg_quality_score": 8.0,  # Better quality
            },
        }

        result = analyzer.detect_winner(experiment_summary)

        assert result["winner"] is None or result["confidence"] == "low"
        assert "tradeoffs" in result

    def test_winner_requires_minimum_samples(self):
        """Cannot detect winner with insufficient samples."""
        analyzer = StatisticalAnalyzer()

        experiment_summary = {
            "control": {
                "count": 15,
                "avg_latency_ms": 50.0,
                "avg_cost_usd": 0.002,
                "avg_quality_score": 7.0,
            },
            "test": {
                "count": 15,
                "avg_latency_ms": 35.0,
                "avg_cost_usd": 0.001,
                "avg_quality_score": 9.0,
            },
        }

        result = analyzer.detect_winner(experiment_summary)

        assert result["winner"] is None
        assert "insufficient_samples" in result["reason"].lower()


class TestMinimumSampleSize:
    """Test minimum sample size calculations."""

    def test_calculate_required_sample_size(self):
        """Calculate required sample size for desired power."""
        analyzer = StatisticalAnalyzer()

        # Detect 20% improvement with 80% power
        required_size = analyzer.calculate_required_sample_size(
            baseline_mean=50.0,
            expected_improvement=0.20,  # 20% improvement
            power=0.80,
            alpha=0.05,
        )

        assert required_size >= 30  # Should need at least 30 samples
        assert isinstance(required_size, int)

    def test_larger_improvement_needs_fewer_samples(self):
        """Larger effect sizes require smaller sample sizes."""
        analyzer = StatisticalAnalyzer()

        # 10% improvement
        size_small_effect = analyzer.calculate_required_sample_size(
            baseline_mean=50.0, expected_improvement=0.10, power=0.80, alpha=0.05
        )

        # 30% improvement
        size_large_effect = analyzer.calculate_required_sample_size(
            baseline_mean=50.0, expected_improvement=0.30, power=0.80, alpha=0.05
        )

        assert size_large_effect < size_small_effect


class TestExperimentAnalysis:
    """Test comprehensive experiment analysis."""

    def test_analyze_complete_experiment(self):
        """Analyze experiment with full statistical report."""
        analyzer = StatisticalAnalyzer()

        experiment_data = {
            "control_latencies": [50, 52, 48, 51, 49] * 20,
            "test_latencies": [35, 37, 33, 36, 34] * 20,
            "control_costs": [0.002] * 100,
            "test_costs": [0.0015] * 100,
            "control_quality": [7, 8, 7, 8, 7] * 20,
            "test_quality": [8, 9, 8, 9, 9] * 20,
        }

        result = analyzer.analyze_experiment(experiment_data)

        assert "latency_analysis" in result
        assert "cost_analysis" in result
        assert "quality_analysis" in result
        assert "overall_winner" in result
        assert "confidence_level" in result
        assert "recommendation" in result

    def test_analyze_experiment_insufficient_data(self):
        """Handle analysis with insufficient data gracefully."""
        analyzer = StatisticalAnalyzer()

        experiment_data = {
            "control_latencies": [50, 51, 52],  # Only 3 samples
            "test_latencies": [45, 46, 47],
        }

        result = analyzer.analyze_experiment(experiment_data)

        assert result["valid"] is False
        assert "insufficient" in result["reason"].lower()


class TestStatisticalReporting:
    """Test human-readable statistical reports."""

    def test_generate_report_with_winner(self):
        """Generate clear report when winner detected."""
        analyzer = StatisticalAnalyzer()

        analysis = {
            "overall_winner": "test",
            "confidence_level": "high",
            "latency_analysis": {"significant": True, "improvement_pct": 30.0},
            "cost_analysis": {"significant": True, "improvement_pct": 25.0},
        }

        report = analyzer.generate_report(analysis)

        assert "test" in report.lower()
        assert "significant" in report.lower()
        assert "30" in report or "latency" in report

    def test_generate_report_no_winner(self):
        """Generate report explaining why no winner detected."""
        analyzer = StatisticalAnalyzer()

        analysis = {
            "overall_winner": None,
            "confidence_level": "low",
            "reason": "Mixed results with tradeoffs",
        }

        report = analyzer.generate_report(analysis)

        assert "no clear winner" in report.lower() or "inconclusive" in report.lower()
