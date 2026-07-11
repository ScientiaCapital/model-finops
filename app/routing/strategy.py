"""Routing strategies."""
import logging
import sqlite3
from abc import ABC, abstractmethod
from app.routing.models import RoutingDecision, RoutingContext
from app.routing.complexity import score_complexity
from app.learning import QueryPatternAnalyzer

logger = logging.getLogger(__name__)


class RoutingStrategy(ABC):
    """Abstract base for routing strategies.

    All routing strategies must implement:
    - route(): Make routing decision for a prompt
    - get_name(): Return strategy identifier for logging
    """

    @abstractmethod
    def route(self, prompt: str, context: RoutingContext) -> RoutingDecision:
        """Route prompt to optimal provider/model.

        Args:
            prompt: User's query text
            context: Additional routing context

        Returns:
            RoutingDecision with provider, model, and metadata

        Raises:
            RoutingError: If strategy cannot make decision
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Return strategy identifier for logging.

        Returns:
            Strategy name (e.g., "complexity", "learning", "hybrid")
        """
        pass


class ComplexityStrategy(RoutingStrategy):
    """Complexity-based routing strategy (baseline).

    Routes based on prompt complexity analysis:
    - Simple (<0.3): Gemini Flash (cheap, fast)
    - Moderate (0.3-0.7): Claude Haiku (balanced)
    - Complex (>0.7): Claude Sonnet (high quality)
    """

    def route(self, prompt: str, context: RoutingContext) -> RoutingDecision:
        """Route based on prompt complexity."""
        complexity_score = score_complexity(prompt)
        fallback_used = False

        # Simple prompts → Gemini (with fallback)
        if complexity_score < 0.3:
            provider, model = self._select_simple_provider(context.available_providers)
            if (provider, model) == (None, None):
                # Fallback to any available provider
                provider, model, fallback_used = self._fallback_provider(context.available_providers)

        # Moderate prompts → Claude Haiku (with fallback)
        elif complexity_score < 0.7:
            provider, model = self._select_moderate_provider(context.available_providers)
            if (provider, model) == (None, None):
                # Fallback to any available provider
                provider, model, fallback_used = self._fallback_provider(context.available_providers)

        # Complex prompts → Claude Sonnet (with fallback)
        else:
            provider, model = self._select_complex_provider(context.available_providers)
            if (provider, model) == (None, None):
                # Fallback to any available provider
                provider, model, fallback_used = self._fallback_provider(context.available_providers)

        return RoutingDecision(
            provider=provider,
            model=model,
            confidence="medium",  # Complexity has medium confidence
            strategy_used="complexity",
            reasoning=f"Complexity score: {complexity_score:.2f}",
            fallback_used=fallback_used,
            metadata={
                "complexity": complexity_score,
                "pattern": "unknown"
            }
        )

    def _select_simple_provider(self, available_providers: list) -> tuple:
        """Select provider for simple prompts with fallback chain.

        Priority: gemini → openrouter/gemini → claude → ollama → deepseek → qwen
        """
        if "gemini" in available_providers:
            return "gemini", "gemini-1.5-flash"

        if "openrouter" in available_providers:
            return "openrouter", "google/gemini-flash-1.5"

        if "claude" in available_providers:
            return "claude", "claude-3-haiku-20240307"

        # Ollama first among new providers for simple work: free/local
        if "ollama" in available_providers:
            return "ollama", "llama3.2"

        # DeepSeek / Qwen: cheap and capable for simple-to-moderate tiers
        if "deepseek" in available_providers:
            return "deepseek", "deepseek-chat"

        if "qwen" in available_providers:
            return "qwen", "qwen-plus"

        return None, None

    def _select_moderate_provider(self, available_providers: list) -> tuple:
        """Select provider for moderate prompts with fallback chain.

        Priority: claude → gemini → openrouter → deepseek → qwen → glm → ollama
        """
        if "claude" in available_providers:
            return "claude", "claude-3-haiku-20240307"

        if "gemini" in available_providers:
            return "gemini", "gemini-1.5-flash"

        if "openrouter" in available_providers:
            return "openrouter", "anthropic/claude-3-haiku"

        # DeepSeek / Qwen: cheap and capable for moderate work
        if "deepseek" in available_providers:
            return "deepseek", "deepseek-chat"

        if "qwen" in available_providers:
            return "qwen", "qwen-plus"

        # GLM: strong agentic model, also viable for moderate work
        if "glm" in available_providers:
            return "glm", "glm-4.7"

        if "ollama" in available_providers:
            return "ollama", "llama3.2"

        return None, None

    def _select_complex_provider(self, available_providers: list) -> tuple:
        """Select provider for complex prompts with fallback chain.

        Priority: claude → gemini → openrouter → glm → deepseek → qwen
        """
        if "claude" in available_providers:
            return "claude", "claude-3-5-sonnet-20241022"

        if "gemini" in available_providers:
            return "gemini", "gemini-1.5-flash"

        if "openrouter" in available_providers:
            return "openrouter", "anthropic/claude-3-sonnet"

        # GLM: strongest of the new providers for complex/agentic work
        if "glm" in available_providers:
            return "glm", "glm-4.7"

        # DeepSeek reasoner / Qwen as further complex-tier fallbacks
        if "deepseek" in available_providers:
            return "deepseek", "deepseek-reasoner"

        if "qwen" in available_providers:
            return "qwen", "qwen-plus"

        return None, None

    def _fallback_provider(self, available_providers: list) -> tuple:
        """Last resort fallback to any available provider.

        Returns: (provider, model, fallback_used)
        """
        if not available_providers:
            raise ValueError("No providers available for routing")

        # Try providers in priority order
        if "gemini" in available_providers:
            return "gemini", "gemini-1.5-flash", True

        if "claude" in available_providers:
            return "claude", "claude-3-haiku-20240307", True

        if "openrouter" in available_providers:
            return "openrouter", "google/gemini-flash-1.5", True

        # New providers as further last-resort options
        if "ollama" in available_providers:
            return "ollama", "llama3.2", True

        if "deepseek" in available_providers:
            return "deepseek", "deepseek-chat", True

        if "qwen" in available_providers:
            return "qwen", "qwen-plus", True

        if "glm" in available_providers:
            return "glm", "glm-4.7", True

        # Use first available as absolute last resort
        provider = available_providers[0]
        return provider, "default", True

    def get_name(self) -> str:
        """Return strategy name."""
        return "complexity"


class LearningStrategy(RoutingStrategy):
    """Pure learning-based routing using QueryPatternAnalyzer.

    Routes based on learned patterns from historical performance data.
    Confidence depends on sample count for detected pattern.
    """

    def __init__(self, db_path: str = "optimizer.db"):
        """Initialize with database path.

        Args:
            db_path: Path to SQLite database with training data
        """
        self.analyzer = QueryPatternAnalyzer(db_path=db_path)

    def route(self, prompt: str, context: RoutingContext) -> RoutingDecision:
        """Route based purely on learned patterns.

        Args:
            prompt: User's query text
            context: Routing context with available providers

        Returns:
            RoutingDecision based on historical performance
        """
        # Identify pattern and get recommendation
        pattern = self.analyzer.identify_pattern(prompt)
        complexity_score = score_complexity(prompt)

        # Convert float complexity score to string category
        if complexity_score < 0.3:
            complexity = "simple"
        elif complexity_score < 0.7:
            complexity = "moderate"
        else:
            complexity = "complex"

        # Try to get recommendation from historical data
        recommendation = None
        try:
            recommendation = self.analyzer.recommend_provider(
                prompt=prompt,
                complexity=complexity,
                available_providers=context.available_providers
            )
        except (sqlite3.Error, FileNotFoundError) as e:
            # Database error or missing table - will use fallback
            logger.debug(f"Could not get recommendation from learning data: {e}")
            pass

        # Handle case when no training data is available or database error
        if recommendation is None:
            # Fallback: use a sensible default based on complexity
            if complexity == "simple":
                provider, model = "gemini", "gemini-1.5-flash"
            elif complexity == "moderate":
                provider, model = "claude", "claude-3-haiku-20240307"
            else:
                provider, model = "claude", "claude-3-5-sonnet-20241022"

            return RoutingDecision(
                provider=provider,
                model=model,
                confidence="low",
                strategy_used="learning",
                reasoning="No training data available, using default",
                fallback_used=True,
                metadata={
                    "pattern": pattern,
                    "quality_score": None,
                    "cost_estimate": None,
                    "complexity": complexity_score
                }
            )

        return RoutingDecision(
            provider=recommendation['provider'],
            model=recommendation['model'],
            confidence=recommendation['confidence'],
            strategy_used="learning",
            reasoning=recommendation.get('reasoning', 'Based on learned patterns'),
            fallback_used=False,
            metadata={
                "pattern": pattern,
                "quality_score": recommendation.get('avg_quality'),
                "composite_score": recommendation.get('score'),
                "cost_estimate": recommendation.get('avg_cost'),
                "complexity": complexity_score
            }
        )

    def get_name(self) -> str:
        """Return strategy name."""
        return "learning"


class HybridStrategy(RoutingStrategy):
    """Hybrid strategy combining learning with complexity validation.

    Routes using learning-based decisions with complexity analysis validation:
    - HIGH confidence: Trust learning completely
    - MEDIUM/LOW confidence: Use learning but mark as experimental
    - No learning data: Fallback to ComplexityStrategy
    """

    def __init__(self, db_path: str = "optimizer.db"):
        """Initialize with database path.

        Args:
            db_path: Path to SQLite database with training data
        """
        self.learning_strategy = LearningStrategy(db_path=db_path)
        self.complexity_strategy = ComplexityStrategy()

    def route(self, prompt: str, context: RoutingContext) -> RoutingDecision:
        """Route using learning with complexity validation.

        Args:
            prompt: User's query text
            context: Routing context with available providers

        Returns:
            RoutingDecision combining learning and complexity insights
        """
        # Get learning recommendation
        try:
            learning_decision = self.learning_strategy.route(prompt, context)
        except Exception as e:
            logger.info(f"Learning strategy failed, falling back to complexity: {e}")
            decision = self.complexity_strategy.route(prompt, context)
            decision.strategy_used = "hybrid_fallback"
            decision.reasoning = f"Fallback to complexity (learning unavailable): {decision.reasoning}"
            return decision

        # Get complexity score for validation
        complexity_score = score_complexity(prompt)

        # HIGH confidence: validate against complexity
        if learning_decision.confidence == "high":
            complexity_decision = self.complexity_strategy.route(prompt, context)

            # Check if recommendations are compatible
            if self._validate_match(learning_decision, complexity_decision):
                learning_decision.strategy_used = "hybrid"
                learning_decision.metadata["complexity"] = complexity_score
                learning_decision.metadata["validation"] = "validated"
                learning_decision.reasoning += " (validated by complexity)"
                return learning_decision
            else:
                # Mismatch - use complexity as safety
                logger.warning(f"Learning/complexity mismatch: {learning_decision.model} vs {complexity_decision.model}")
                complexity_decision.strategy_used = "hybrid"
                complexity_decision.metadata["learning_mismatch"] = True
                complexity_decision.metadata["rejected_model"] = learning_decision.model
                return complexity_decision

        # MEDIUM/LOW confidence: use learning but mark as experimental
        else:
            learning_decision.strategy_used = "hybrid"
            learning_decision.confidence = "medium"  # Cap at medium for safety
            learning_decision.metadata["complexity"] = complexity_score
            learning_decision.metadata["validation"] = "experimental"
            learning_decision.metadata["experimental"] = True
            learning_decision.reasoning = f"Experimental routing (confidence={learning_decision.confidence}): {learning_decision.reasoning}"
            return learning_decision

    def get_name(self) -> str:
        """Return strategy name."""
        return "hybrid"

    def _validate_match(
        self,
        learning: RoutingDecision,
        complexity: RoutingDecision
    ) -> bool:
        """Check if learning and complexity recommendations are compatible.

        Compatible means within 1 tier of each other:
        - Simple tier: gemini-1.5-flash
        - Moderate tier: claude-3-haiku-20240307, deepseek-chat
        - Complex tier: claude-3-5-sonnet-20241022, qwen-2-72b

        Args:
            learning: Learning strategy decision
            complexity: Complexity strategy decision

        Returns:
            True if recommendations are within 1 tier of each other
        """
        # Define tier mapping
        tier_map = {
            "gemini-1.5-flash": "simple",
            "claude-3-haiku-20240307": "moderate",
            "claude-3-5-sonnet-20241022": "complex",
            "openrouter/deepseek/deepseek-chat": "moderate",
            "openrouter/qwen/qwen-2-72b-instruct": "complex",
            "google/gemini-flash-1.5": "simple",
            "anthropic/claude-3-haiku": "moderate",
            "anthropic/claude-3.5-haiku": "moderate",
        }

        learning_tier = tier_map.get(learning.model, "moderate")
        complexity_tier = tier_map.get(complexity.model, "moderate")

        # Allow same tier or one tier difference
        tier_order = ["simple", "moderate", "complex"]
        learning_idx = tier_order.index(learning_tier)
        complexity_idx = tier_order.index(complexity_tier)

        return abs(learning_idx - complexity_idx) <= 1
