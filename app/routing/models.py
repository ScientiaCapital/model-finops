"""Data models for routing system."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RoutingDecision:
    """Represents a routing decision with metadata.

    Attributes:
        provider: Provider name (e.g., "gemini", "claude", "openrouter")
        model: Full model name (e.g., "gemini-flash", "openrouter/deepseek-chat")
        confidence: Confidence level ("high", "medium", "low")
        strategy_used: Strategy that made decision ("learning", "complexity", "hybrid")
        reasoning: Human-readable explanation of decision
        fallback_used: True if strategy failed and used fallback
        metadata: Additional context (pattern, quality_score, cost_estimate, etc.)
    """

    provider: str
    model: str
    confidence: str
    strategy_used: str
    reasoning: str
    fallback_used: bool
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RoutingContext:
    """Context passed to routing strategies.

    Attributes:
        prompt: User's query text
        user_id: Optional user identifier
        session_id: Optional session identifier
        available_providers: List of providers available for routing
        max_cost: Optional maximum cost constraint
        min_quality: Optional minimum quality constraint
    """

    prompt: str
    user_id: str | None = None
    session_id: str | None = None
    available_providers: list[str] = field(
        default_factory=lambda: [
            "gemini",
            "claude",
            "openrouter",
            "ollama",
            "deepseek",
            "glm",
            "qwen",
        ]
    )
    max_cost: float | None = None
    min_quality: float | None = None
