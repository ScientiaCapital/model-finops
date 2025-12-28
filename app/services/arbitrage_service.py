"""
Arbitrage Service - Business logic for cost optimization through model switching.

Provides methods to analyze prompts, find cheaper alternatives, and track savings.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from app.models.arbitrage import (
    ModelCapability,
    CapabilityLevel,
    ModelProfile,
    ArbitrageOpportunity,
    ArbitrageAnalysisRequest,
    ArbitrageAnalysisResponse,
)
from app.arbitrage.capability_registry import CapabilityRegistry, CAPABILITY_LEVEL_ORDER

logger = logging.getLogger(__name__)


class ArbitrageService:
    """
    Service for detecting and tracking arbitrage opportunities.

    Analyzes requests to find cheaper model alternatives with
    equivalent capabilities.
    """

    def __init__(self, supabase_client=None):
        """
        Initialize arbitrage service.

        Args:
            supabase_client: Optional Supabase client for persistence
        """
        self.registry = CapabilityRegistry()
        self.supabase = supabase_client
        self._quality_threshold = 0.85  # Minimum quality score for alternatives

    async def analyze_prompt(
        self,
        prompt: str,
        current_model: str,
        user_id: Optional[str] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> ArbitrageAnalysisResponse:
        """
        Analyze a prompt to find cost optimization opportunities.

        Args:
            prompt: The prompt text to analyze
            current_model: Model currently being used
            user_id: Optional user ID for tracking
            input_tokens: Estimated input tokens
            output_tokens: Estimated output tokens

        Returns:
            ArbitrageAnalysisResponse with opportunities
        """
        # Get current model profile
        current_profile = self.registry.get_model_profile(current_model)
        if not current_profile:
            logger.warning(f"Model not in registry: {current_model}")
            return ArbitrageAnalysisResponse(
                request_id=str(uuid4()),
                current_model=current_model,
                current_cost=0.0,
                opportunities=[],
                max_savings_percent=0.0,
                recommendation=None,
                analyzed_at=datetime.utcnow(),
            )

        # Detect required capabilities from prompt
        detected_capabilities = self._detect_capabilities(prompt)

        # Calculate current cost
        if input_tokens == 0:
            input_tokens = len(prompt) // 4  # Rough estimate
        if output_tokens == 0:
            output_tokens = input_tokens  # Assume similar output

        current_cost = current_profile.calculate_cost(input_tokens, output_tokens)

        # Find cheaper alternatives
        alternatives = self.registry.get_cheaper_alternatives(
            model_id=current_model,
            required_capabilities=detected_capabilities,
        )

        # Build opportunity list
        opportunities = []
        for alt in alternatives:
            alt_cost = alt.calculate_cost(input_tokens, output_tokens)
            savings_percent = ((current_cost - alt_cost) / current_cost * 100
                               if current_cost > 0 else 0)

            # Get capability match quality
            quality_score = self._calculate_quality_match(
                current_profile, alt, detected_capabilities
            )

            # Only include if quality is acceptable
            if quality_score >= self._quality_threshold:
                opportunity = ArbitrageOpportunity(
                    id=str(uuid4()),
                    current_model=current_model,
                    alternative_model=alt.model_id,
                    current_provider=current_profile.provider,
                    alternative_provider=alt.provider,
                    current_cost=current_cost,
                    alternative_cost=alt_cost,
                    savings_percent=savings_percent,
                    quality_score=quality_score,
                    required_capabilities=detected_capabilities,
                )
                opportunities.append(opportunity)

        # Sort by savings (highest first)
        opportunities.sort(key=lambda x: x.savings_percent, reverse=True)

        # Build response
        max_savings = opportunities[0].savings_percent if opportunities else 0.0
        recommendation = opportunities[0] if opportunities else None

        response = ArbitrageAnalysisResponse(
            request_id=str(uuid4()),
            current_model=current_model,
            current_cost=current_cost,
            opportunities=opportunities,
            max_savings_percent=max_savings,
            recommendation=recommendation,
            analyzed_at=datetime.utcnow(),
        )

        # Log opportunity for tracking
        if opportunities and user_id and self.supabase:
            await self._log_opportunity(user_id, response)

        return response

    def _detect_capabilities(self, prompt: str) -> List[ModelCapability]:
        """
        Detect required capabilities from prompt content.

        Uses keyword matching for capability detection.
        """
        prompt_lower = prompt.lower()
        capabilities = []

        # Code-related keywords
        code_keywords = [
            "code", "function", "class", "implement", "program",
            "debug", "fix bug", "refactor", "syntax", "compile",
            "python", "javascript", "typescript", "java", "rust",
        ]
        if any(kw in prompt_lower for kw in code_keywords):
            capabilities.append(ModelCapability.CODE_GEN)

        # Code review keywords
        review_keywords = ["review", "critique", "improve", "optimize code"]
        if any(kw in prompt_lower for kw in review_keywords):
            capabilities.append(ModelCapability.CODE_REVIEW)

        # Reasoning keywords
        reasoning_keywords = [
            "explain", "why", "analyze", "reason", "think",
            "consider", "evaluate", "compare", "contrast",
        ]
        if any(kw in prompt_lower for kw in reasoning_keywords):
            capabilities.append(ModelCapability.REASONING)

        # Math keywords
        math_keywords = [
            "calculate", "math", "equation", "formula", "number",
            "algebra", "calculus", "statistics", "probability",
        ]
        if any(kw in prompt_lower for kw in math_keywords):
            capabilities.append(ModelCapability.MATH)

        # Creative keywords
        creative_keywords = [
            "write", "story", "creative", "imagine", "poem",
            "narrative", "fiction", "generate text",
        ]
        if any(kw in prompt_lower for kw in creative_keywords):
            capabilities.append(ModelCapability.CREATIVE)

        # Analysis keywords
        analysis_keywords = [
            "analyze", "summarize", "extract", "insight",
            "data", "pattern", "trend",
        ]
        if any(kw in prompt_lower for kw in analysis_keywords):
            capabilities.append(ModelCapability.ANALYSIS)

        # Translation keywords
        translation_keywords = [
            "translate", "translation", "language", "spanish",
            "french", "german", "chinese", "japanese",
        ]
        if any(kw in prompt_lower for kw in translation_keywords):
            capabilities.append(ModelCapability.TRANSLATION)

        # Summarization keywords
        summarize_keywords = ["summarize", "summary", "brief", "tldr", "key points"]
        if any(kw in prompt_lower for kw in summarize_keywords):
            capabilities.append(ModelCapability.SUMMARIZATION)

        # JSON mode keywords
        json_keywords = ["json", "structured", "schema", "format as"]
        if any(kw in prompt_lower for kw in json_keywords):
            capabilities.append(ModelCapability.JSON_MODE)

        # Default to reasoning if no specific capability detected
        if not capabilities:
            capabilities.append(ModelCapability.REASONING)

        return list(set(capabilities))

    def _calculate_quality_match(
        self,
        current: ModelProfile,
        alternative: ModelProfile,
        required_capabilities: List[ModelCapability],
    ) -> float:
        """
        Calculate quality match between current and alternative model.

        Returns a score from 0.0 to 1.0 based on capability levels.
        """
        if not required_capabilities:
            return 0.5  # No capabilities to compare

        scores = []
        for cap in required_capabilities:
            current_level = current.capabilities.get(cap)
            alt_level = alternative.capabilities.get(cap)

            if not alt_level:
                scores.append(0.0)  # Missing capability
            elif not current_level:
                scores.append(1.0)  # Alternative has it, current doesn't
            else:
                # Compare levels
                current_score = CAPABILITY_LEVEL_ORDER.get(current_level, 0)
                alt_score = CAPABILITY_LEVEL_ORDER.get(alt_level, 0)

                if alt_score >= current_score:
                    scores.append(1.0)  # Equal or better
                else:
                    # Partial score based on difference
                    diff = current_score - alt_score
                    scores.append(max(0, 1.0 - (diff * 0.25)))

        return sum(scores) / len(scores) if scores else 0.5

    async def _log_opportunity(
        self,
        user_id: str,
        response: ArbitrageAnalysisResponse,
    ):
        """Log arbitrage opportunity to database."""
        if not self.supabase or not response.opportunities:
            return

        try:
            best = response.recommendation or response.opportunities[0]
            await self.supabase.table("arbitrage_opportunities").insert({
                "user_id": user_id,
                "request_id": response.request_id,
                "current_model": response.current_model,
                "alternative_model": best.alternative_model,
                "current_cost": response.current_cost,
                "alternative_cost": best.alternative_cost,
                "savings_percent": best.savings_percent,
                "required_capabilities": [c.value for c in best.required_capabilities],
                "was_applied": False,
            }).execute()
        except Exception as e:
            logger.error(f"Failed to log arbitrage opportunity: {e}")

    async def get_user_opportunities(
        self,
        user_id: str,
        limit: int = 20,
    ) -> List[Dict]:
        """Get recent arbitrage opportunities for a user."""
        if not self.supabase:
            return []

        try:
            result = await self.supabase.table("arbitrage_opportunities") \
                .select("*") \
                .eq("user_id", user_id) \
                .order("created_at", desc=True) \
                .limit(limit) \
                .execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to get opportunities: {e}")
            return []

    async def get_savings_report(self, user_id: str, days: int = 30) -> Dict:
        """
        Generate savings report for a user.

        Returns potential vs actual savings over time.
        """
        if not self.supabase:
            return {
                "total_potential_savings": 0.0,
                "actual_savings": 0.0,
                "opportunities_found": 0,
                "opportunities_applied": 0,
            }

        try:
            result = await self.supabase.table("arbitrage_opportunities") \
                .select("*") \
                .eq("user_id", user_id) \
                .execute()

            opportunities = result.data or []
            total_potential = sum(
                o.get("current_cost", 0) - o.get("alternative_cost", 0)
                for o in opportunities
            )
            applied = [o for o in opportunities if o.get("was_applied")]
            actual_savings = sum(
                o.get("current_cost", 0) - o.get("alternative_cost", 0)
                for o in applied
            )

            return {
                "total_potential_savings": total_potential,
                "actual_savings": actual_savings,
                "opportunities_found": len(opportunities),
                "opportunities_applied": len(applied),
                "savings_rate": (actual_savings / total_potential * 100
                                 if total_potential > 0 else 0),
            }
        except Exception as e:
            logger.error(f"Failed to generate savings report: {e}")
            return {
                "total_potential_savings": 0.0,
                "actual_savings": 0.0,
                "opportunities_found": 0,
                "opportunities_applied": 0,
            }

    def get_alternatives_for_model(
        self,
        model_id: str,
        capabilities: Optional[List[ModelCapability]] = None,
    ) -> List[ModelProfile]:
        """
        Get cheaper alternatives for a specific model.

        Args:
            model_id: The model to find alternatives for
            capabilities: Optional filter by required capabilities

        Returns:
            List of cheaper model profiles
        """
        if capabilities is None:
            # Get all capabilities from current model
            profile = self.registry.get_model_profile(model_id)
            if profile:
                capabilities = list(profile.capabilities.keys())
            else:
                capabilities = []

        return self.registry.get_cheaper_alternatives(
            model_id=model_id,
            required_capabilities=capabilities,
        )
