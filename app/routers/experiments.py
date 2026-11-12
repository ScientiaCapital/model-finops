"""
Experiment API Router

REST API endpoints for A/B testing experiments.
"""

import logging
import os

from fastapi import APIRouter, HTTPException, status

from app.experiments.statistical_analyzer import StatisticalAnalyzer
from app.experiments.tracker import ExperimentTracker
from app.models.experiments import (
    ExperimentAnalysisResponse,
    ExperimentComplete,
    ExperimentCompleteResponse,
    ExperimentCreate,
    ExperimentListResponse,
    ExperimentProgressResponse,
    ExperimentResponse,
    ExperimentResult,
    ExperimentResultResponse,
    ExperimentSummaryResponse,
    UserAssignmentResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/experiments", tags=["experiments"])

# Initialize tracker and analyzer (use production database)
tracker = ExperimentTracker(db_path=os.getenv("DATABASE_PATH", "optimizer.db"))
analyzer = StatisticalAnalyzer()


@router.post("", response_model=ExperimentResponse, status_code=status.HTTP_201_CREATED)
def create_experiment(experiment: ExperimentCreate) -> ExperimentResponse:
    """
    Create a new A/B test experiment.

    Args:
        experiment: Experiment configuration

    Returns:
        Created experiment details

    Raises:
        HTTPException 400: If control and test strategies are the same
    """
    # Additional validation: strategies must be different
    if experiment.control_strategy == experiment.test_strategy:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Control and test strategies must be different "
                f"(both are '{experiment.control_strategy}')"
            ),
        )

    try:
        experiment_id = tracker.create_experiment(
            name=experiment.name,
            control_strategy=experiment.control_strategy,
            test_strategy=experiment.test_strategy,
            sample_size=experiment.sample_size,
            status="active",
        )

        return ExperimentResponse(
            experiment_id=experiment_id,
            name=experiment.name,
            control_strategy=experiment.control_strategy,
            test_strategy=experiment.test_strategy,
            sample_size=experiment.sample_size,
            status="active",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get("/active", response_model=ExperimentListResponse)
def get_active_experiments() -> ExperimentListResponse:
    """
    List all active experiments.

    Returns:
        List of active experiments
    """
    experiments = tracker.get_active_experiments()
    return ExperimentListResponse(experiments=experiments)


@router.post("/{experiment_id}/complete", response_model=ExperimentCompleteResponse)
def complete_experiment(
    experiment_id: int, completion: ExperimentComplete
) -> ExperimentCompleteResponse:
    """
    Mark experiment as completed.

    Args:
        experiment_id: ID of experiment to complete
        completion: Completion details including winner

    Returns:
        Updated experiment status

    Raises:
        HTTPException 404: If experiment not found
    """
    # Verify experiment exists first
    progress = tracker.get_experiment_progress(experiment_id)
    if progress["sample_size"] == 0:  # Experiment doesn't exist
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Experiment {experiment_id} not found"
        )

    try:
        tracker.complete_experiment(experiment_id, winner=completion.winner)

        return ExperimentCompleteResponse(
            experiment_id=experiment_id, status="completed", winner=completion.winner
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to complete experiment {experiment_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete experiment",
        ) from e


@router.get("/{experiment_id}/assign/{user_id}", response_model=UserAssignmentResponse)
def assign_user(experiment_id: int, user_id: str) -> UserAssignmentResponse:
    """
    Assign user to control or test group.

    Uses deterministic hashing - same user always gets same assignment.

    Args:
        experiment_id: ID of experiment
        user_id: User identifier

    Returns:
        Assigned strategy for the user

    Raises:
        HTTPException 404: If experiment not found
    """
    try:
        strategy = tracker.assign_user(experiment_id, user_id)

        return UserAssignmentResponse(
            experiment_id=experiment_id, user_id=user_id, strategy=strategy
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post(
    "/{experiment_id}/results",
    response_model=ExperimentResultResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_result(experiment_id: int, result: ExperimentResult) -> ExperimentResultResponse:
    """
    Record an experiment result (routing decision outcome).

    Args:
        experiment_id: ID of experiment
        result: Result details

    Returns:
        Result ID

    Raises:
        HTTPException 404: If experiment not found
    """
    try:
        result_id = tracker.record_result(
            experiment_id=experiment_id,
            user_id=result.user_id,
            strategy_assigned=result.strategy_assigned,
            latency_ms=result.latency_ms,
            cost_usd=result.cost_usd,
            quality_score=result.quality_score,
            provider=result.provider,
            model=result.model,
        )

        return ExperimentResultResponse(result_id=result_id, experiment_id=experiment_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to record result for experiment {experiment_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record experiment result",
        ) from e


@router.get("/{experiment_id}/summary", response_model=ExperimentSummaryResponse)
def get_summary(experiment_id: int) -> ExperimentSummaryResponse:
    """
    Get aggregated statistics by strategy.

    Args:
        experiment_id: ID of experiment

    Returns:
        Aggregated stats for control and test groups
    """
    summary = tracker.get_experiment_summary(experiment_id)
    return ExperimentSummaryResponse(**summary)


@router.get("/{experiment_id}/progress", response_model=ExperimentProgressResponse)
def get_progress(experiment_id: int) -> ExperimentProgressResponse:
    """
    Get progress toward sample size goal.

    Args:
        experiment_id: ID of experiment

    Returns:
        Progress information
    """
    progress = tracker.get_experiment_progress(experiment_id)
    return ExperimentProgressResponse(**progress)


@router.post("/{experiment_id}/analyze", response_model=ExperimentAnalysisResponse)
def analyze_experiment(experiment_id: int) -> ExperimentAnalysisResponse:
    """
    Run statistical analysis on experiment results.

    Performs chi-square and t-tests to determine if test strategy
    significantly outperforms control.

    Args:
        experiment_id: ID of experiment

    Returns:
        Statistical analysis results

    Raises:
        HTTPException 400: If insufficient data for analysis
    """
    # Get experiment summary
    summary = tracker.get_experiment_summary(experiment_id)

    # Check minimum sample size (30 per group)
    control_count = summary["control"]["count"]
    test_count = summary["test"]["count"]

    if control_count < 30 or test_count < 30:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Insufficient data for analysis (need 30 samples per group, "
                f"got control={control_count}, test={test_count})"
            ),
        )

    # Prepare data for analysis (we don't have raw values, only aggregates)
    # For now, we'll use the winner detection based on aggregate stats
    winner_result = analyzer.detect_winner(summary)

    # Build response
    return ExperimentAnalysisResponse(
        valid=True,
        overall_winner=winner_result.get("winner"),
        confidence_level=winner_result.get("confidence"),
        recommendation=(
            f"Winner: {winner_result.get('winner')} (confidence: {winner_result.get('confidence')})"
            if winner_result.get("winner")
            else "No clear winner detected"
        ),
    )
