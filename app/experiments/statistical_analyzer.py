"""
StatisticalAnalyzer - Statistical Significance Testing for A/B Experiments

Provides scientific validation of A/B test results:
- Chi-square tests for categorical outcomes (success/failure rates)
- T-tests for continuous metrics (latency, cost, quality)
- Winner detection with confidence levels
- Minimum sample size calculations
- Effect size measurements (Cohen's d)
"""

import logging
import math
from typing import Any

import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)

# Minimum sample size for statistical validity
MIN_SAMPLE_SIZE = 30
SIGNIFICANCE_LEVEL = 0.05  # p-value threshold (95% confidence)


class StatisticalAnalyzer:
    """
    Analyzes A/B test results for statistical significance.

    Provides chi-square tests for categorical data and t-tests
    for continuous metrics, with automatic winner detection.
    """

    def chi_square_test(
        self, control_successes: int, control_total: int, test_successes: int, test_total: int
    ) -> dict[str, Any]:
        """
        Perform chi-square test for categorical outcomes.

        Tests whether success rates are significantly different between
        control and test groups.

        Args:
            control_successes: Number of successes in control group
            control_total: Total trials in control group
            test_successes: Number of successes in test group
            test_total: Total trials in test group

        Returns:
            Dict with:
            - significant: bool (p < 0.05)
            - p_value: float
            - chi_square_statistic: float
            - control_rate: float (success rate)
            - test_rate: float (success rate)

        Raises:
            ValueError: If sample sizes too small (< 30)
        """
        # Validate sample sizes
        if control_total < MIN_SAMPLE_SIZE or test_total < MIN_SAMPLE_SIZE:
            raise ValueError(
                f"Insufficient sample size. Need at least {MIN_SAMPLE_SIZE} "
                f"samples per group. Got control={control_total}, test={test_total}"
            )

        # Calculate success rates
        control_rate = control_successes / control_total
        test_rate = test_successes / test_total

        # Build contingency table:
        # [[control_successes, control_failures],
        #  [test_successes, test_failures]]
        control_failures = control_total - control_successes
        test_failures = test_total - test_successes

        contingency_table = [[control_successes, control_failures], [test_successes, test_failures]]

        # Handle zero variance edge cases (all successes or all failures in both groups)
        if (control_failures == 0 and test_failures == 0) or (
            control_successes == 0 and test_successes == 0
        ):
            # Both groups identical (all success or all fail) - no difference
            return {
                "significant": False,
                "p_value": 1.0,
                "chi_square_statistic": 0.0,
                "control_rate": control_rate,
                "test_rate": test_rate,
            }

        # Warn if one group has extreme rates (potential chi-square assumption violation)
        if (
            control_failures == 0
            or test_failures == 0
            or control_successes == 0
            or test_successes == 0
        ):
            logger.warning(
                f"Chi-square test with extreme success rates "
                f"(control={control_rate:.2%}, test={test_rate:.2%}). "
                f"Results may be unreliable due to low expected cell counts."
            )

        # Perform chi-square test
        chi2_statistic, p_value, dof, expected = stats.chi2_contingency(contingency_table)

        logger.debug(
            f"Chi-square test: control_rate={control_rate:.3f}, "
            f"test_rate={test_rate:.3f}, p={p_value:.4f}"
        )

        return {
            "significant": bool(p_value < SIGNIFICANCE_LEVEL),
            "p_value": float(p_value),
            "chi_square_statistic": float(chi2_statistic),
            "control_rate": control_rate,
            "test_rate": test_rate,
        }

    def ttest_independent(
        self, control_values: list[float], test_values: list[float], metric_name: str
    ) -> dict[str, Any]:
        """
        Perform independent t-test for continuous metrics.

        Tests whether means are significantly different between
        control and test groups.

        Args:
            control_values: List of measurements from control group
            test_values: List of measurements from test group
            metric_name: Name of metric being tested (for logging)

        Returns:
            Dict with:
            - significant: bool (p < 0.05)
            - p_value: float
            - control_mean: float
            - test_mean: float
            - effect_size: float (Cohen's d)

        Raises:
            ValueError: If sample sizes too small (< 30)
        """
        # Validate sample sizes
        if len(control_values) < MIN_SAMPLE_SIZE or len(test_values) < MIN_SAMPLE_SIZE:
            raise ValueError(
                f"Insufficient sample size for {metric_name}. "
                f"Need at least {MIN_SAMPLE_SIZE} samples per group. "
                f"Got control={len(control_values)}, test={len(test_values)}"
            )

        # Calculate means
        control_mean = sum(control_values) / len(control_values)
        test_mean = sum(test_values) / len(test_values)

        # Perform independent t-test
        t_statistic, p_value = stats.ttest_ind(control_values, test_values)

        # Calculate Cohen's d (effect size)
        control_std = np.std(control_values, ddof=1)
        test_std = np.std(test_values, ddof=1)
        pooled_std = math.sqrt((control_std**2 + test_std**2) / 2)

        if pooled_std > 0:
            cohens_d = abs(control_mean - test_mean) / pooled_std
        else:
            # Zero variance case: all values identical
            # If means differ, effect size is very large; otherwise zero
            # 10.0 stands in for an arbitrarily large effect (perfect separation)
            cohens_d = 10.0 if abs(control_mean - test_mean) > 1e-9 else 0.0

        logger.debug(
            f"T-test for {metric_name}: control_mean={control_mean:.4f}, "
            f"test_mean={test_mean:.4f}, p={p_value:.4f}, d={cohens_d:.2f}"
        )

        return {
            "significant": bool(p_value < SIGNIFICANCE_LEVEL),
            "p_value": float(p_value),
            "control_mean": float(control_mean),
            "test_mean": float(test_mean),
            "effect_size": float(cohens_d),
        }

    def detect_winner(self, experiment_summary: dict[str, dict[str, Any]]) -> dict[str, Any]:
        """
        Detect winner based on multiple metrics.

        Analyzes latency, cost, and quality to determine if test strategy
        significantly outperforms control across all metrics.

        Args:
            experiment_summary: Dict with 'control' and 'test' keys, each containing:
                - count: number of samples
                - avg_latency_ms: average latency
                - avg_cost_usd: average cost
                - avg_quality_score: average quality

        Returns:
            Dict with:
            - winner: 'test', 'control', or None
            - confidence: 'high', 'medium', 'low'
            - winning_metrics: list of metrics where winner excels
            - tradeoffs: dict of mixed results (if any)
            - reason: explanation if no clear winner
        """
        control = experiment_summary.get("control", {})
        test = experiment_summary.get("test", {})

        # Check minimum samples
        control_count = control.get("count", 0)
        test_count = test.get("count", 0)

        if control_count < MIN_SAMPLE_SIZE or test_count < MIN_SAMPLE_SIZE:
            return {
                "winner": None,
                "confidence": "low",
                "winning_metrics": [],
                "tradeoffs": {},
                "reason": f"insufficient_samples (need {MIN_SAMPLE_SIZE} per group)",
            }

        # Compare metrics
        winning_metrics = []
        tradeoffs = {}

        # Latency (lower is better)
        if test.get("avg_latency_ms", float("inf")) < control.get("avg_latency_ms", 0):
            winning_metrics.append("latency")
        elif test.get("avg_latency_ms", 0) > control.get("avg_latency_ms", float("inf")):
            tradeoffs["latency"] = "control_better"

        # Cost (lower is better)
        if test.get("avg_cost_usd", float("inf")) < control.get("avg_cost_usd", 0):
            winning_metrics.append("cost")
        elif test.get("avg_cost_usd", 0) > control.get("avg_cost_usd", float("inf")):
            tradeoffs["cost"] = "control_better"

        # Quality (higher is better)
        if test.get("avg_quality_score", 0) > control.get("avg_quality_score", float("inf")):
            winning_metrics.append("quality")
        elif test.get("avg_quality_score", float("inf")) < control.get("avg_quality_score", 0):
            tradeoffs["quality"] = "control_better"

        # Determine winner and confidence
        if len(winning_metrics) == 3 and len(tradeoffs) == 0:
            # Test wins on all metrics
            return {
                "winner": "test",
                "confidence": "high",
                "winning_metrics": winning_metrics,
                "tradeoffs": tradeoffs,
            }
        elif len(winning_metrics) >= 2 and len(tradeoffs) == 0:
            # Test wins on most metrics with no tradeoffs
            return {
                "winner": "test",
                "confidence": "medium",
                "winning_metrics": winning_metrics,
                "tradeoffs": tradeoffs,
            }
        elif len(tradeoffs) > 0:
            # Mixed results - any tradeoff means unclear winner
            return {
                "winner": None,
                "confidence": "low",
                "winning_metrics": winning_metrics,
                "tradeoffs": tradeoffs,
                "reason": "Mixed results with tradeoffs",
            }
        else:
            # No clear difference
            return {
                "winner": None,
                "confidence": "low",
                "winning_metrics": [],
                "tradeoffs": {},
                "reason": "No significant differences detected",
            }

    def calculate_required_sample_size(
        self,
        baseline_mean: float,
        expected_improvement: float,
        power: float = 0.80,
        alpha: float = 0.05,
    ) -> int:
        """
        Calculate required sample size for desired statistical power.

        Uses power analysis to determine how many samples are needed to
        detect a given effect size with specified confidence.

        Args:
            baseline_mean: Current average value
            expected_improvement: Expected relative improvement (e.g., 0.20 for 20%)
            power: Desired statistical power (1 - beta), typically 0.80
            alpha: Significance level, typically 0.05

        Returns:
            Required sample size per group (integer)
        """
        # Calculate effect size (Cohen's d)
        # Assuming std dev is ~30% of mean (conservative estimate)
        assumed_std = baseline_mean * 0.30
        expected_diff = baseline_mean * expected_improvement

        # 0.5 is the default moderate effect when no spread is assumed
        cohens_d = expected_diff / assumed_std if assumed_std > 0 else 0.5

        # Power analysis formula (simplified)
        # n ≈ 2 * ((Z_α/2 + Z_β) / d)^2
        # Where Z_α/2 is critical value for alpha/2, Z_β for power

        z_alpha = stats.norm.ppf(1 - alpha / 2)  # ~1.96 for alpha=0.05
        z_beta = stats.norm.ppf(power)  # ~0.84 for power=0.80

        if cohens_d > 0:
            n = 2 * ((z_alpha + z_beta) / cohens_d) ** 2
            required_size = int(math.ceil(n))
        else:
            required_size = 100  # Default conservative size

        # Enforce minimum
        required_size = max(required_size, MIN_SAMPLE_SIZE)

        logger.info(
            f"Required sample size: {required_size} per group "
            f"(improvement={expected_improvement:.1%}, power={power:.2f})"
        )

        return required_size

    def analyze_experiment(self, experiment_data: dict[str, list[float]]) -> dict[str, Any]:
        """
        Perform comprehensive experiment analysis.

        Analyzes all available metrics and provides overall recommendation.

        Args:
            experiment_data: Dict with keys like:
                - control_latencies: List[float]
                - test_latencies: List[float]
                - control_costs: List[float]
                - test_costs: List[float]
                - control_quality: List[int]
                - test_quality: List[int]

        Returns:
            Dict with:
            - latency_analysis: t-test results
            - cost_analysis: t-test results
            - quality_analysis: t-test results
            - overall_winner: 'test', 'control', or None
            - confidence_level: 'high', 'medium', 'low'
            - recommendation: text summary
            - valid: bool (whether analysis is valid)
            - reason: explanation if invalid
        """
        # Check if we have minimum data
        control_latencies = experiment_data.get("control_latencies", [])
        test_latencies = experiment_data.get("test_latencies", [])

        if len(control_latencies) < MIN_SAMPLE_SIZE or len(test_latencies) < MIN_SAMPLE_SIZE:
            return {
                "valid": False,
                "reason": f"Insufficient data (need {MIN_SAMPLE_SIZE} samples per group)",
            }

        # Analyze each metric
        analyses = {}

        if "control_latencies" in experiment_data and "test_latencies" in experiment_data:
            analyses["latency_analysis"] = self.ttest_independent(
                experiment_data["control_latencies"],
                experiment_data["test_latencies"],
                "latency_ms",
            )
            # Add improvement percentage (safe division)
            if analyses["latency_analysis"]["control_mean"] > 0:
                analyses["latency_analysis"]["improvement_pct"] = (
                    (
                        analyses["latency_analysis"]["control_mean"]
                        - analyses["latency_analysis"]["test_mean"]
                    )
                    / analyses["latency_analysis"]["control_mean"]
                    * 100
                )
            else:
                analyses["latency_analysis"]["improvement_pct"] = 0.0

        if "control_costs" in experiment_data and "test_costs" in experiment_data:
            analyses["cost_analysis"] = self.ttest_independent(
                experiment_data["control_costs"], experiment_data["test_costs"], "cost_usd"
            )
            # Add improvement percentage (safe division)
            if analyses["cost_analysis"]["control_mean"] > 0:
                analyses["cost_analysis"]["improvement_pct"] = (
                    (
                        analyses["cost_analysis"]["control_mean"]
                        - analyses["cost_analysis"]["test_mean"]
                    )
                    / analyses["cost_analysis"]["control_mean"]
                    * 100
                )
            else:
                analyses["cost_analysis"]["improvement_pct"] = 0.0

        if "control_quality" in experiment_data and "test_quality" in experiment_data:
            analyses["quality_analysis"] = self.ttest_independent(
                experiment_data["control_quality"], experiment_data["test_quality"], "quality_score"
            )

        # Determine overall winner
        significant_improvements = 0
        significant_regressions = 0

        for metric, analysis in analyses.items():
            if analysis["significant"]:
                if "latency" in metric or "cost" in metric:
                    # Lower is better
                    if analysis["test_mean"] < analysis["control_mean"]:
                        significant_improvements += 1
                    else:
                        significant_regressions += 1
                else:
                    # Higher is better (quality)
                    if analysis["test_mean"] > analysis["control_mean"]:
                        significant_improvements += 1
                    else:
                        significant_regressions += 1

        # Determine winner
        if significant_improvements > 0 and significant_regressions == 0:
            overall_winner = "test"
            confidence_level = "high" if significant_improvements >= 2 else "medium"
        elif significant_regressions > significant_improvements:
            overall_winner = "control"
            confidence_level = "medium"
        else:
            overall_winner = None
            confidence_level = "low"

        # Generate recommendation
        if overall_winner == "test":
            recommendation = (
                f"Test strategy shows significant improvements across "
                f"{significant_improvements} metric(s). Recommend adopting test strategy."
            )
        elif overall_winner == "control":
            recommendation = "Control strategy performs better. Keep existing approach."
        else:
            recommendation = (
                "No clear winner. Consider extending experiment or analyzing tradeoffs."
            )

        return {
            **analyses,
            "overall_winner": overall_winner,
            "confidence_level": confidence_level,
            "recommendation": recommendation,
            "valid": True,
        }

    def generate_report(self, analysis: dict[str, Any]) -> str:
        """
        Generate human-readable report from analysis results.

        Args:
            analysis: Output from analyze_experiment()

        Returns:
            Formatted text report
        """
        if not analysis.get("valid", True):
            return f"⚠️  Analysis Invalid: {analysis.get('reason', 'Unknown reason')}"

        winner = analysis.get("overall_winner")
        confidence = analysis.get("confidence_level", "unknown")

        if winner == "test":
            report = f"✅ **Winner: TEST Strategy** (Confidence: {confidence.upper()})\n\n"
            report += "Significant improvements detected:\n"

            if "latency_analysis" in analysis and analysis["latency_analysis"].get("significant"):
                improvement = analysis["latency_analysis"].get("improvement_pct", 0)
                report += f"  • Latency: {improvement:.1f}% faster\n"

            if "cost_analysis" in analysis and analysis["cost_analysis"].get("significant"):
                improvement = analysis["cost_analysis"].get("improvement_pct", 0)
                report += f"  • Cost: {improvement:.1f}% cheaper\n"

        elif winner == "control":
            report = f"⚠️  **Winner: CONTROL Strategy** (Confidence: {confidence.upper()})\n\n"
            report += "Test strategy did not outperform control.\n"

        else:
            report = f"❓ **No Clear Winner** (Confidence: {confidence.upper()})\n\n"
            reason = analysis.get("reason", "Mixed results or insufficient differences")
            report += f"Reason: {reason}\n"

        return report
