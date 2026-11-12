"""Automated learning pipeline from user feedback."""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any

from app.learning.query_pattern_analyzer import QueryPatternAnalyzer
from app.services.admin_service import get_admin_service

logger = logging.getLogger(__name__)


def _is_sqlite(conn: object) -> bool:
    """Check if connection is SQLite."""
    return hasattr(conn, "row_factory")


class FeedbackTrainer:
    """Retrains routing recommendations from user feedback.

    Uses confidence-based thresholds to only update routing when
    sufficient quality feedback has been collected.
    """

    # Confidence thresholds
    HIGH_CONFIDENCE_THRESHOLD = 10
    MEDIUM_CONFIDENCE_THRESHOLD = 5
    MIN_QUALITY_SCORE = 3.5
    MIN_CORRECTNESS_RATE = 0.7

    def __init__(self) -> None:
        """Initialize trainer with database connection."""
        self.analyzer = QueryPatternAnalyzer(db_path=None)  # Uses PostgreSQL

    def retrain(self, dry_run: bool = False) -> dict[str, Any]:
        """Run retraining cycle.

        Args:
            dry_run: If True, preview changes without applying

        Returns:
            Retraining summary with changes made
        """
        run_id = str(uuid.uuid4())
        logger.info(f"Starting retraining run {run_id} (dry_run={dry_run})")

        # 1. Aggregate feedback by pattern + model
        performance_data = self._aggregate_feedback()

        changes = []

        # 2. Compute confidence and update routing
        for pattern, models_data in performance_data.items():
            for model, stats in models_data.items():
                confidence = self._calculate_confidence(
                    sample_count=stats["count"],
                    avg_quality=stats["avg_quality"],
                    correctness_rate=stats["correctness"],
                )

                # 3. Only update if meets threshold
                if confidence in ["high", "medium"]:
                    change = {
                        "pattern": pattern,
                        "model": model,
                        "confidence": confidence,
                        "sample_count": stats["count"],
                        "avg_quality": stats["avg_quality"],
                        "correctness_rate": stats["correctness"],
                    }

                    changes.append(change)

                    if not dry_run:
                        self._update_routing_weights(pattern, model, stats)
                        self._store_performance_history(pattern, model, stats, confidence, run_id)

        # 4. Log retraining run
        result = {
            "run_id": run_id,
            "timestamp": datetime.now().isoformat(),
            "patterns_updated": len(set(c["pattern"] for c in changes)),
            "total_changes": len(changes),
            "changes": changes,
            "dry_run": dry_run,
        }

        if not dry_run:
            self._log_retraining_run(result)

        logger.info(f"Retraining complete: {result['total_changes']} changes")

        return result

    def _calculate_confidence(
        self, sample_count: int, avg_quality: float, correctness_rate: float
    ) -> str:
        """Calculate confidence level for pattern.

        Args:
            sample_count: Number of feedback samples
            avg_quality: Average quality score (1-5)
            correctness_rate: Correctness rate (0-1)

        Returns:
            Confidence level: 'high', 'medium', or 'low'
        """
        # Check quality thresholds
        if avg_quality < self.MIN_QUALITY_SCORE or correctness_rate < self.MIN_CORRECTNESS_RATE:
            return "low"

        # High confidence: lots of samples + excellent metrics
        if (
            sample_count >= self.HIGH_CONFIDENCE_THRESHOLD
            and avg_quality >= 4.0
            and correctness_rate >= 0.8
        ):
            return "high"

        # Medium confidence: sufficient samples + good metrics
        if sample_count >= self.MEDIUM_CONFIDENCE_THRESHOLD:
            return "medium"

        # Low confidence: insufficient data
        return "low"

    def _aggregate_feedback(self) -> dict[str, dict[str, dict[str, Any]]]:
        """Aggregate feedback by pattern and model.

        Returns:
            Nested dict: {pattern: {model: {stats}}}
        """
        admin_service = get_admin_service()

        # Run async operation in sync context
        try:
            # Check if event loop is already running
            asyncio.get_running_loop()
            # Event loop is running - create task and wait
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, admin_service.aggregate_feedback_for_learning())
                result = future.result()
                return result
        except RuntimeError:
            # No running loop - safe to use asyncio.run()
            result = asyncio.run(admin_service.aggregate_feedback_for_learning())
            return result

    def _update_routing_weights(self, pattern: str, model: str, stats: dict[str, Any]) -> None:
        """Update routing weights for pattern-model pair.

        Args:
            pattern: Prompt pattern
            model: Model name
            stats: Performance statistics
        """
        # Update QueryPatternAnalyzer weights
        # This is application-specific logic
        logger.info(
            f"Updating weights for {pattern} -> {model}: quality={stats['avg_quality']:.2f}"
        )

        # Implementation depends on how QueryPatternAnalyzer stores recommendations
        # For now, just log the update
        pass

    def _store_performance_history(
        self, pattern: str, model: str, stats: dict[str, Any], confidence: str, run_id: str
    ) -> None:
        """Store performance metrics to history table.

        Args:
            pattern: Prompt pattern
            model: Model name
            stats: Performance statistics
            confidence: Confidence level
            run_id: Retraining run ID
        """
        admin_service = get_admin_service()

        # Run async operation in sync context
        try:
            # Check if event loop is already running
            asyncio.get_running_loop()
            # Event loop is running - create task in thread pool
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    admin_service.store_performance_history(
                        pattern=pattern,
                        model=model,
                        stats=stats,
                        confidence=confidence,
                        run_id=run_id,
                    ),
                )
                future.result()
        except RuntimeError:
            # No running loop - safe to use asyncio.run()
            asyncio.run(
                admin_service.store_performance_history(
                    pattern=pattern, model=model, stats=stats, confidence=confidence, run_id=run_id
                )
            )

    def _log_retraining_run(self, result: dict[str, Any]) -> None:
        """Log retraining run metadata.

        Args:
            result: Retraining result summary
        """
        logger.info(f"Retraining run {result['run_id']}: {result['total_changes']} changes applied")

    def _get_current_weights(self) -> dict[str, Any]:
        """Get current routing weights for comparison.

        Returns:
            Current weights
        """
        # Placeholder for getting current state
        return {}
