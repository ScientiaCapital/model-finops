"""
Basic usage example for AI Stack Optimizer.

This example shows how to:
1. Track LLM costs
2. Track voice AI costs
3. Set and enforce budgets
4. Get cost summaries

Note: This example uses core components only (no langchain dependency).
For LangGraph integration, install langchain-core and langgraph.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from langgraph_cost_optimizer import (
    CostTracker,
    BudgetEnforcer,
    BudgetExceededError,
    calculate_cost,
    calculate_audio_tts_cost,
    calculate_audio_stt_cost,
    get_model_pricing,
    get_service_pricing,
    get_all_providers,
)


def main():
    print("=" * 60)
    print("AI Stack Optimizer - Basic Usage Example")
    print("=" * 60)

    # 1. List all supported providers
    print("\n1. Supported Providers:")
    print(f"   {', '.join(get_all_providers())}")

    # 2. Check pricing for specific models
    print("\n2. Model Pricing:")
    models = ["claude-sonnet-4-5", "deepseek/deepseek-chat", "llama-3.3-70b-versatile"]
    for model in models:
        pricing = get_model_pricing(model)
        if pricing:
            print(f"   {model}: ${pricing.input_price:.2f}/${pricing.output_price:.2f} per 1M tokens")

    # 3. Calculate LLM costs
    print("\n3. LLM Cost Calculations:")
    costs = [
        ("claude-sonnet-4-5", 10000, 5000),
        ("deepseek/deepseek-chat", 10000, 5000),
        ("llama-3.3-70b-versatile", 10000, 5000),
    ]
    for model, inp, out in costs:
        cost = calculate_cost(model, inp, out)
        print(f"   {model}: {inp} in + {out} out = ${cost:.6f}")

    # 4. Calculate voice AI costs
    print("\n4. Voice AI Cost Calculations:")
    print(f"   Cartesia TTS (30 sec): ${calculate_audio_tts_cost('cartesia', seconds=30):.4f}")
    print(f"   Deepgram STT (5 min): ${calculate_audio_stt_cost('deepgram', minutes=5):.4f}")

    # 5. Use CostTracker with budget enforcement
    print("\n5. Budget Enforcement Demo:")

    def on_warning(budget_type, entity_name, current, limit):
        print(f"   WARNING: {budget_type} at {current/limit*100:.0f}% (${current:.4f}/${limit:.4f})")

    tracker = CostTracker()
    enforcer = BudgetEnforcer(
        tracker=tracker,
        total_budget_usd=0.10,  # $0.10 budget for demo
        per_agent_budget_usd=0.05,
        warning_threshold=0.5,  # Warn at 50%
        on_warning=on_warning,
    )

    # Record some costs
    agents = ["researcher", "writer", "reviewer"]
    for i, agent in enumerate(agents):
        tracker.record(
            model_id="claude-haiku-4-5",
            input_tokens=5000 * (i + 1),
            output_tokens=2000 * (i + 1),
            agent_name=agent,
        )

    # Check budget
    try:
        enforcer.check_budget()
        print("   Budget check passed!")
    except BudgetExceededError as e:
        print(f"   Budget EXCEEDED: {e.budget_type} - ${e.current_cost:.4f} >= ${e.budget_limit:.4f}")

    # 6. Get summary
    print("\n6. Cost Summary:")
    summary = tracker.get_summary()
    print(f"   Total Cost: ${summary['total_cost_usd']:.4f}")
    print(f"   Total Tokens: {summary['total_tokens']:,}")
    print(f"   API Calls: {summary['num_calls']}")
    print("\n   By Agent:")
    for agent, data in summary['by_agent'].items():
        print(f"      {agent}: ${data['cost_usd']:.4f} ({data['calls']} calls)")
    print("\n   Remaining Budget:")
    remaining = enforcer.get_remaining_budget()
    if 'total' in remaining:
        print(f"      Total: ${remaining['total']:.4f}")

    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
