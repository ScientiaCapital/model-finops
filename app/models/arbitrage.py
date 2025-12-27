"""
Pydantic models for Provider Arbitrage Detection.

Defines model capabilities, equivalency groups, and arbitrage recommendations.
"""
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class ModelCapability(str, Enum):
    """Capabilities that AI models can have."""
    CODE_GEN = "code_gen"
    CODE_REVIEW = "code_review"
    REASONING = "reasoning"
    MATH = "math"
    CREATIVE = "creative"
    ANALYSIS = "analysis"
    TRANSLATION = "translation"
    SUMMARIZATION = "summarization"
    VISION = "vision"
    AUDIO = "audio"
    FUNCTION_CALLING = "function_calling"
    JSON_MODE = "json_mode"


class CapabilityLevel(str, Enum):
    """Quality level for a capability."""
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class ModelProfile(BaseModel):
    """Profile of an AI model with capabilities and pricing."""
    provider: str
    model_id: str
    capabilities: Dict[ModelCapability, CapabilityLevel] = Field(default_factory=dict)
    input_price_per_million: float = Field(..., ge=0)
    output_price_per_million: float = Field(..., ge=0)
    context_window: int = Field(..., gt=0)
    avg_latency_ms: Optional[int] = None

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for given token counts."""
        input_cost = (input_tokens / 1_000_000) * self.input_price_per_million
        output_cost = (output_tokens / 1_000_000) * self.output_price_per_million
        return input_cost + output_cost


class EquivalencyGroup(BaseModel):
    """Group of models with equivalent capability for a task type."""
    capability: ModelCapability
    quality_tier: str
    models: List[str] = Field(..., min_length=1)


class ArbitrageOpportunity(BaseModel):
    """A detected arbitrage opportunity between models."""
    id: str = ""
    current_model: str
    current_provider: str
    alternative_model: str
    alternative_provider: str
    current_cost: float = Field(..., ge=0)
    alternative_cost: float = Field(..., ge=0)
    savings_percent: float = Field(..., ge=0, le=100)
    quality_score: float = Field(..., ge=0, le=1)
    required_capabilities: List[ModelCapability] = Field(default_factory=list)


class ArbitrageRecommendation(BaseModel):
    """Recommendation response from arbitrage analysis."""
    prompt_preview: str
    detected_task_type: str
    opportunities: List[ArbitrageOpportunity] = Field(default_factory=list)
    best_opportunity: Optional[ArbitrageOpportunity] = None
    total_savings_potential: float = Field(default=0.0, ge=0)
    recommendation_reasoning: str


class ArbitrageAnalysisRequest(BaseModel):
    """Request to analyze a prompt for arbitrage opportunities."""
    prompt: str = Field(..., min_length=1)
    current_model: str
    input_tokens: Optional[int] = Field(default=None, ge=1)
    output_tokens: Optional[int] = Field(default=None, ge=1)
    min_quality_threshold: float = Field(default=0.85, ge=0, le=1)


class ArbitrageAnalysisResponse(BaseModel):
    """Response from arbitrage analysis."""
    request_id: str
    current_model: str
    current_cost: float = Field(..., ge=0)
    opportunities: List[ArbitrageOpportunity] = Field(default_factory=list)
    max_savings_percent: float = Field(default=0.0, ge=0)
    recommendation: Optional[ArbitrageOpportunity] = None
    analyzed_at: datetime


class SavingsReport(BaseModel):
    """Report of savings over a time period."""
    period_days: int
    total_requests: int
    actual_cost: float
    optimal_cost: float
    potential_savings: float
    savings_percentage: float
    opportunities_detected: int
    opportunities_applied: int

    @property
    def application_rate(self) -> float:
        """Percentage of opportunities that were applied."""
        if self.opportunities_detected == 0:
            return 0.0
        return (self.opportunities_applied / self.opportunities_detected) * 100


class ModelAlternative(BaseModel):
    """A cheaper alternative model for the current one."""
    provider: str
    model_id: str
    input_price_per_million: float
    output_price_per_million: float
    savings_vs_current: float = Field(..., ge=0, le=100)
    quality_score: float = Field(..., ge=0, le=1)
    supported_capabilities: List[str]
    context_window: int
    avg_latency_ms: Optional[int] = None
