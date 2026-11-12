"""Scheduled retraining with APScheduler."""

import logging
from typing import Any

from apscheduler.job import Job
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.learning.feedback_trainer import FeedbackTrainer

logger = logging.getLogger(__name__)


class RetrainingScheduler:
    """Manages scheduled retraining jobs.

    Default schedule: Every Sunday at 2:00 AM
    """

    def __init__(self, cron_schedule: str = "0 2 * * 0") -> None:
        """Initialize scheduler.

        Args:
            cron_schedule: Cron expression for retraining schedule
                          Default: "0 2 * * 0" (Sundays at 2 AM)
        """
        self.scheduler = BackgroundScheduler()
        self.trainer = FeedbackTrainer()
        self.cron_schedule = cron_schedule

        # Add retraining job
        self.scheduler.add_job(
            func=self._run_retraining,
            trigger=CronTrigger.from_crontab(cron_schedule),
            id="weekly_retraining",
            name="Weekly Feedback Retraining",
            replace_existing=True,
        )

    def start(self) -> None:
        """Start scheduler."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info(f"Retraining scheduler started: {self.cron_schedule}")

    def stop(self) -> None:
        """Stop scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Retraining scheduler stopped")

    def is_running(self) -> bool:
        """Check if scheduler is running.

        Returns:
            True if running
        """
        return self.scheduler.running

    def get_jobs(self) -> list[Job]:
        """Get scheduled jobs.

        Returns:
            List of scheduled jobs
        """
        return self.scheduler.get_jobs()

    def trigger_immediate_retraining(self, dry_run: bool = False) -> dict[str, Any]:
        """Manually trigger retraining immediately.

        Args:
            dry_run: If True, preview changes without applying

        Returns:
            Retraining result
        """
        logger.info(f"Manual retraining triggered (dry_run={dry_run})")
        return self._run_retraining(dry_run=dry_run)

    def _run_retraining(self, dry_run: bool = False) -> dict[str, Any]:
        """Run retraining job.

        Args:
            dry_run: If True, preview changes only

        Returns:
            Retraining result
        """
        try:
            logger.info("Starting scheduled retraining...")
            result = self.trainer.retrain(dry_run=dry_run)

            logger.info(
                f"Retraining complete: {result['total_changes']} changes, "
                f"{result['patterns_updated']} patterns updated"
            )

            return result

        except Exception as e:
            logger.error(f"Retraining failed: {e}", exc_info=True)
            raise
