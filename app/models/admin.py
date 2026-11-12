"""Pydantic models for admin endpoints."""

from typing import Any

from pydantic import BaseModel


class FeedbackSummary(BaseModel):
    """Summary of feedback statistics."""

    total_feedback: int
    avg_quality_score: float
    models: list[dict[str, Any]]


class LearningStatus(BaseModel):
    """Status of learning pipeline."""

    last_retraining_run: str | None
    next_scheduled_run: str | None
    confidence_distribution: dict[str, int]
    total_patterns: int


class RetrainingResult(BaseModel):
    """Result of retraining run."""

    run_id: str
    timestamp: str
    patterns_updated: int
    total_changes: int
    changes: list[dict[str, Any]]
    dry_run: bool


class PerformanceTrends(BaseModel):
    """Performance trends for a pattern."""

    pattern: str
    trends: list[dict[str, Any]]
