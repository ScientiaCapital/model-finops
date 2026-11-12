"""Pydantic models for feedback."""

from pydantic import BaseModel, Field


class FeedbackRequest(BaseModel):
    """Request model for submitting feedback."""

    request_id: str = Field(..., description="Request ID from routing decision")
    quality_score: int = Field(..., ge=1, le=5, description="Quality rating 1-5")
    is_correct: bool = Field(..., description="Was response factually correct")
    is_helpful: bool | None = Field(None, description="Was response helpful")
    comment: str | None = Field(None, max_length=1000, description="Optional comment")


class FeedbackResponse(BaseModel):
    """Response model for feedback submission."""

    status: str = Field(..., description="Status of submission")
    feedback_id: int = Field(..., description="ID of stored feedback")
    message: str = Field(..., description="Human-readable message")
