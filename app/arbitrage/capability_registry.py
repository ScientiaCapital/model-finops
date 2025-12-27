"""
Capability Registry for Model Arbitrage.

Maps AI models to their capabilities, pricing, and specifications.
Enables finding cheaper alternatives with equivalent capabilities.
"""
from typing import Dict, List, Optional
from app.models.arbitrage import ModelProfile, ModelCapability, CapabilityLevel


# Capability level ordering for comparisons
CAPABILITY_LEVEL_ORDER = {
    CapabilityLevel.BASIC: 0,
    CapabilityLevel.INTERMEDIATE: 1,
    CapabilityLevel.ADVANCED: 2,
    CapabilityLevel.EXPERT: 3,
}


class CapabilityRegistry:
    """
    Registry of AI model capabilities and pricing.

    Provides methods to find models by capability, compare pricing,
    and discover cheaper alternatives.
    """

    def __init__(self):
        """Initialize registry with predefined model profiles."""
        self._models: Dict[str, ModelProfile] = {}
        self._load_default_models()

    def _load_default_models(self):
        """Load predefined model profiles with current pricing."""
        models = [
            # Gemini Models
            ModelProfile(
                provider="gemini",
                model_id="gemini-1.5-flash",
                capabilities={
                    ModelCapability.CODE_GEN: CapabilityLevel.INTERMEDIATE,
                    ModelCapability.REASONING: CapabilityLevel.INTERMEDIATE,
                    ModelCapability.CREATIVE: CapabilityLevel.INTERMEDIATE,
                    ModelCapability.ANALYSIS: CapabilityLevel.INTERMEDIATE,
                    ModelCapability.SUMMARIZATION: CapabilityLevel.ADVANCED,
                    ModelCapability.MATH: CapabilityLevel.INTERMEDIATE,
                    ModelCapability.VISION: CapabilityLevel.INTERMEDIATE,
                    ModelCapability.JSON_MODE: CapabilityLevel.ADVANCED,
                },
                input_price_per_million=0.075,
                output_price_per_million=0.30,
                context_window=1_000_000,
                avg_latency_ms=400,
            ),
            ModelProfile(
                provider="gemini",
                model_id="gemini-1.5-pro",
                capabilities={
                    ModelCapability.CODE_GEN: CapabilityLevel.ADVANCED,
                    ModelCapability.REASONING: CapabilityLevel.ADVANCED,
                    ModelCapability.CREATIVE: CapabilityLevel.ADVANCED,
                    ModelCapability.ANALYSIS: CapabilityLevel.ADVANCED,
                    ModelCapability.SUMMARIZATION: CapabilityLevel.ADVANCED,
                    ModelCapability.MATH: CapabilityLevel.ADVANCED,
                    ModelCapability.VISION: CapabilityLevel.ADVANCED,
                    ModelCapability.JSON_MODE: CapabilityLevel.ADVANCED,
                },
                input_price_per_million=1.25,
                output_price_per_million=5.00,
                context_window=2_000_000,
                avg_latency_ms=600,
            ),

            # Anthropic Models
            ModelProfile(
                provider="anthropic",
                model_id="claude-3-5-sonnet-20241022",
                capabilities={
                    ModelCapability.CODE_GEN: CapabilityLevel.EXPERT,
                    ModelCapability.CODE_REVIEW: CapabilityLevel.EXPERT,
                    ModelCapability.REASONING: CapabilityLevel.EXPERT,
                    ModelCapability.CREATIVE: CapabilityLevel.EXPERT,
                    ModelCapability.ANALYSIS: CapabilityLevel.EXPERT,
                    ModelCapability.SUMMARIZATION: CapabilityLevel.EXPERT,
                    ModelCapability.MATH: CapabilityLevel.ADVANCED,
                    ModelCapability.VISION: CapabilityLevel.ADVANCED,
                    ModelCapability.JSON_MODE: CapabilityLevel.EXPERT,
                    ModelCapability.FUNCTION_CALLING: CapabilityLevel.EXPERT,
                },
                input_price_per_million=3.00,
                output_price_per_million=15.00,
                context_window=200_000,
                avg_latency_ms=800,
            ),
            ModelProfile(
                provider="anthropic",
                model_id="claude-3-5-haiku-20241022",
                capabilities={
                    ModelCapability.CODE_GEN: CapabilityLevel.INTERMEDIATE,
                    ModelCapability.REASONING: CapabilityLevel.INTERMEDIATE,
                    ModelCapability.CREATIVE: CapabilityLevel.INTERMEDIATE,
                    ModelCapability.ANALYSIS: CapabilityLevel.INTERMEDIATE,
                    ModelCapability.SUMMARIZATION: CapabilityLevel.ADVANCED,
                    ModelCapability.JSON_MODE: CapabilityLevel.ADVANCED,
                    ModelCapability.FUNCTION_CALLING: CapabilityLevel.INTERMEDIATE,
                },
                input_price_per_million=0.80,
                output_price_per_million=4.00,
                context_window=200_000,
                avg_latency_ms=300,
            ),

            # Groq Models (fast inference)
            ModelProfile(
                provider="groq",
                model_id="llama-3.3-70b-versatile",
                capabilities={
                    ModelCapability.CODE_GEN: CapabilityLevel.ADVANCED,
                    ModelCapability.REASONING: CapabilityLevel.ADVANCED,
                    ModelCapability.CREATIVE: CapabilityLevel.INTERMEDIATE,
                    ModelCapability.ANALYSIS: CapabilityLevel.ADVANCED,
                    ModelCapability.SUMMARIZATION: CapabilityLevel.ADVANCED,
                    ModelCapability.MATH: CapabilityLevel.INTERMEDIATE,
                    ModelCapability.JSON_MODE: CapabilityLevel.INTERMEDIATE,
                },
                input_price_per_million=0.59,
                output_price_per_million=0.79,
                context_window=128_000,
                avg_latency_ms=150,
            ),
            ModelProfile(
                provider="groq",
                model_id="llama-3.1-8b-instant",
                capabilities={
                    ModelCapability.CODE_GEN: CapabilityLevel.BASIC,
                    ModelCapability.REASONING: CapabilityLevel.BASIC,
                    ModelCapability.CREATIVE: CapabilityLevel.BASIC,
                    ModelCapability.SUMMARIZATION: CapabilityLevel.INTERMEDIATE,
                    ModelCapability.JSON_MODE: CapabilityLevel.BASIC,
                },
                input_price_per_million=0.05,
                output_price_per_million=0.08,
                context_window=128_000,
                avg_latency_ms=80,
            ),
            ModelProfile(
                provider="groq",
                model_id="mixtral-8x7b-32768",
                capabilities={
                    ModelCapability.CODE_GEN: CapabilityLevel.INTERMEDIATE,
                    ModelCapability.REASONING: CapabilityLevel.INTERMEDIATE,
                    ModelCapability.CREATIVE: CapabilityLevel.INTERMEDIATE,
                    ModelCapability.MATH: CapabilityLevel.INTERMEDIATE,
                    ModelCapability.JSON_MODE: CapabilityLevel.INTERMEDIATE,
                },
                input_price_per_million=0.24,
                output_price_per_million=0.24,
                context_window=32_768,
                avg_latency_ms=120,
            ),

            # Cerebras Models (ultra-fast)
            ModelProfile(
                provider="cerebras",
                model_id="llama3.1-70b",
                capabilities={
                    ModelCapability.CODE_GEN: CapabilityLevel.ADVANCED,
                    ModelCapability.REASONING: CapabilityLevel.ADVANCED,
                    ModelCapability.CREATIVE: CapabilityLevel.INTERMEDIATE,
                    ModelCapability.ANALYSIS: CapabilityLevel.ADVANCED,
                    ModelCapability.MATH: CapabilityLevel.INTERMEDIATE,
                },
                input_price_per_million=0.60,
                output_price_per_million=0.60,
                context_window=128_000,
                avg_latency_ms=100,
            ),
            ModelProfile(
                provider="cerebras",
                model_id="llama3.1-8b",
                capabilities={
                    ModelCapability.CODE_GEN: CapabilityLevel.BASIC,
                    ModelCapability.REASONING: CapabilityLevel.BASIC,
                    ModelCapability.SUMMARIZATION: CapabilityLevel.INTERMEDIATE,
                },
                input_price_per_million=0.10,
                output_price_per_million=0.10,
                context_window=128_000,
                avg_latency_ms=50,
            ),

            # OpenRouter Models
            ModelProfile(
                provider="openrouter",
                model_id="openrouter/gpt-3.5-turbo",
                capabilities={
                    ModelCapability.CODE_GEN: CapabilityLevel.INTERMEDIATE,
                    ModelCapability.REASONING: CapabilityLevel.INTERMEDIATE,
                    ModelCapability.CREATIVE: CapabilityLevel.INTERMEDIATE,
                    ModelCapability.FUNCTION_CALLING: CapabilityLevel.ADVANCED,
                    ModelCapability.JSON_MODE: CapabilityLevel.ADVANCED,
                },
                input_price_per_million=0.50,
                output_price_per_million=1.50,
                context_window=16_384,
                avg_latency_ms=400,
            ),
            ModelProfile(
                provider="openrouter",
                model_id="openrouter/mistral-7b-instruct",
                capabilities={
                    ModelCapability.CODE_GEN: CapabilityLevel.BASIC,
                    ModelCapability.REASONING: CapabilityLevel.BASIC,
                    ModelCapability.CREATIVE: CapabilityLevel.BASIC,
                    ModelCapability.SUMMARIZATION: CapabilityLevel.INTERMEDIATE,
                },
                input_price_per_million=0.07,
                output_price_per_million=0.07,
                context_window=32_768,
                avg_latency_ms=200,
            ),

            # DeepSeek Models
            ModelProfile(
                provider="deepseek",
                model_id="deepseek-chat",
                capabilities={
                    ModelCapability.CODE_GEN: CapabilityLevel.ADVANCED,
                    ModelCapability.REASONING: CapabilityLevel.ADVANCED,
                    ModelCapability.ANALYSIS: CapabilityLevel.ADVANCED,
                    ModelCapability.MATH: CapabilityLevel.ADVANCED,
                    ModelCapability.JSON_MODE: CapabilityLevel.INTERMEDIATE,
                },
                input_price_per_million=0.14,
                output_price_per_million=0.28,
                context_window=64_000,
                avg_latency_ms=500,
            ),
            ModelProfile(
                provider="deepseek",
                model_id="deepseek-coder",
                capabilities={
                    ModelCapability.CODE_GEN: CapabilityLevel.EXPERT,
                    ModelCapability.CODE_REVIEW: CapabilityLevel.ADVANCED,
                    ModelCapability.REASONING: CapabilityLevel.INTERMEDIATE,
                },
                input_price_per_million=0.14,
                output_price_per_million=0.28,
                context_window=64_000,
                avg_latency_ms=450,
            ),
        ]

        for model in models:
            self._models[model.model_id] = model

    def get_all_models(self) -> List[ModelProfile]:
        """Get all registered model profiles."""
        return list(self._models.values())

    def get_model_profile(self, model_id: str) -> Optional[ModelProfile]:
        """Get profile for a specific model by ID."""
        return self._models.get(model_id)

    def get_models_with_capability(
        self,
        capability: ModelCapability,
        min_level: Optional[CapabilityLevel] = None
    ) -> List[ModelProfile]:
        """
        Get models that have a specific capability.

        Args:
            capability: The capability to filter by
            min_level: Minimum capability level required (optional)

        Returns:
            List of models with the capability at or above min_level
        """
        result = []
        for model in self._models.values():
            if capability in model.capabilities:
                model_level = model.capabilities[capability]
                if min_level is None:
                    result.append(model)
                elif CAPABILITY_LEVEL_ORDER[model_level] >= CAPABILITY_LEVEL_ORDER[min_level]:
                    result.append(model)
        return result

    def get_models_by_provider(self, provider: str) -> List[ModelProfile]:
        """Get all models from a specific provider."""
        return [m for m in self._models.values() if m.provider == provider]

    def get_cheaper_alternatives(
        self,
        model_id: str,
        required_capabilities: List[ModelCapability],
        min_level: Optional[CapabilityLevel] = None
    ) -> List[ModelProfile]:
        """
        Find cheaper alternatives to a model with required capabilities.

        Args:
            model_id: The current model to find alternatives for
            required_capabilities: Capabilities the alternative must have
            min_level: Minimum level for all required capabilities

        Returns:
            List of cheaper alternatives sorted by input price (cheapest first)
        """
        current = self.get_model_profile(model_id)
        if not current:
            return []

        alternatives = []
        for model in self._models.values():
            # Skip the current model
            if model.model_id == model_id:
                continue

            # Must be cheaper
            if model.input_price_per_million >= current.input_price_per_million:
                continue

            # Must have all required capabilities
            has_all = True
            for cap in required_capabilities:
                if cap not in model.capabilities:
                    has_all = False
                    break
                if min_level and CAPABILITY_LEVEL_ORDER[model.capabilities[cap]] < CAPABILITY_LEVEL_ORDER[min_level]:
                    has_all = False
                    break

            if has_all:
                alternatives.append(model)

        # Sort by price (cheapest first)
        alternatives.sort(key=lambda m: m.input_price_per_million)
        return alternatives

    def get_cheapest_model(
        self,
        capability: ModelCapability,
        min_level: Optional[CapabilityLevel] = None
    ) -> Optional[ModelProfile]:
        """
        Find the cheapest model with a specific capability.

        Args:
            capability: Required capability
            min_level: Minimum capability level

        Returns:
            The cheapest model with the capability, or None
        """
        candidates = self.get_models_with_capability(capability, min_level)
        if not candidates:
            return None

        return min(candidates, key=lambda m: m.input_price_per_million)
