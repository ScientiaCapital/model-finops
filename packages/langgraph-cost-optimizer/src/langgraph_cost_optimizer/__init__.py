"""
AI Stack Optimizer - Comprehensive cost tracking for your entire AI/ML stack.

Tracks costs across:
- LLMs: Anthropic, OpenAI, Google, Groq, Cerebras, DeepSeek, Qwen
- Voice: Cartesia, ElevenLabs, Deepgram, AssemblyAI
- Infrastructure: Supabase, Vercel
- Observability: LangSmith

Usage:
    from langgraph_cost_optimizer import LangGraphCostOptimizer

    optimizer = LangGraphCostOptimizer(
        total_budget_usd=100.0,
        per_agent_budget_usd=20.0
    )

    # Track LangGraph costs automatically
    tracked_graph = optimizer.wrap(compiled_graph)
    result = tracked_graph.invoke(input)

    # Track audio costs manually
    optimizer.record_manual(
        model_id="cartesia/sonic-english",
        input_tokens=0,
        output_tokens=0,
        metadata={"audio_seconds": 30.0, "cost_usd": 1.26}
    )

    print(optimizer.get_summary())  # Full breakdown by service, agent, model
"""

__version__ = "0.1.0"

# Core imports (no langchain dependency)
from langgraph_cost_optimizer.tracker import CostTracker, CostRecord
from langgraph_cost_optimizer.budget import BudgetEnforcer, BudgetExceededError
from langgraph_cost_optimizer.providers import (
    # LLM pricing
    PROVIDER_PRICING,
    ModelPricing,
    get_model_pricing,
    calculate_cost,
    get_cheapest_model,
    # Service pricing (audio, infra)
    SERVICE_PRICING,
    ServicePricing,
    PricingUnit,
    get_service_pricing,
    calculate_service_cost,
    calculate_audio_tts_cost,
    calculate_audio_stt_cost,
    get_all_providers,
)

# Lazy imports for langchain-dependent components
def __getattr__(name):
    """Lazy load langchain-dependent components."""
    if name == "LangGraphCostOptimizer":
        from langgraph_cost_optimizer.middleware import LangGraphCostOptimizer
        return LangGraphCostOptimizer
    if name == "CostTrackingCallback":
        from langgraph_cost_optimizer.callbacks import CostTrackingCallback
        return CostTrackingCallback
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    # Main interface (lazy loaded)
    "LangGraphCostOptimizer",
    "CostTrackingCallback",
    # Core components
    "CostTracker",
    "CostRecord",
    "BudgetEnforcer",
    "BudgetExceededError",
    # LLM pricing
    "PROVIDER_PRICING",
    "ModelPricing",
    "get_model_pricing",
    "calculate_cost",
    "get_cheapest_model",
    # Service pricing
    "SERVICE_PRICING",
    "ServicePricing",
    "PricingUnit",
    "get_service_pricing",
    "calculate_service_cost",
    "calculate_audio_tts_cost",
    "calculate_audio_stt_cost",
    "get_all_providers",
]
