# AI Stack Optimizer

> Comprehensive cost tracking and budget enforcement for your entire AI/ML stack.

Track costs across LLMs, voice AI, infrastructure, and observability tools - all in one place.

## Features

- **LLM Cost Tracking**: Anthropic Claude, OpenAI, Google Gemini, Groq, Cerebras, DeepSeek, Qwen
- **Voice AI**: Cartesia TTS, ElevenLabs TTS, Deepgram STT, AssemblyAI STT
- **Infrastructure**: Supabase (database, auth, storage), Vercel (serverless, edge)
- **Observability**: LangSmith traces
- **Budget Enforcement**: Set limits per agent, per model, or globally
- **LangGraph Integration**: Automatic tracking via callbacks

## Installation

```bash
pip install langgraph-cost-optimizer

# With SQLite persistence
pip install langgraph-cost-optimizer[sqlite]
```

## Quick Start

### Basic Usage

```python
from langgraph_cost_optimizer import (
    LangGraphCostOptimizer,
    calculate_cost,
    calculate_audio_tts_cost,
    calculate_audio_stt_cost,
)

# Create optimizer with budget limits
optimizer = LangGraphCostOptimizer(
    total_budget_usd=100.0,      # $100 total budget
    per_agent_budget_usd=20.0,   # $20 per agent
    warning_threshold=0.8,        # Warn at 80%
)

# Track LLM calls
optimizer.record_manual(
    model_id="claude-sonnet-4-5",
    input_tokens=1000,
    output_tokens=500,
    agent_name="researcher",
)

# Track voice costs
tts_cost = calculate_audio_tts_cost("cartesia", seconds=30)
stt_cost = calculate_audio_stt_cost("deepgram", minutes=5)

print(optimizer.get_summary())
```

### LangGraph Integration

```python
from langgraph.graph import StateGraph
from langgraph_cost_optimizer import LangGraphCostOptimizer

# Build your graph
graph = StateGraph(AgentState)
graph.add_node("researcher", researcher_node)
graph.add_node("writer", writer_node)
compiled = graph.compile()

# Wrap with cost tracking
optimizer = LangGraphCostOptimizer(
    total_budget_usd=50.0,
    per_agent_budget_usd=10.0,
)
tracked_graph = optimizer.wrap(compiled)

# Use normally - costs tracked automatically
result = tracked_graph.invoke({"query": "Research AI trends"})

# Get cost breakdown
print(optimizer.get_summary())
# {
#   "total_cost_usd": 0.0234,
#   "by_agent": {"researcher": {"cost_usd": 0.018}, "writer": {"cost_usd": 0.0054}},
#   "by_model": {"claude-sonnet-4-5": {...}},
#   "remaining_budget": {"total": 49.98, ...}
# }
```

### Budget Enforcement

```python
from langgraph_cost_optimizer import BudgetExceededError

try:
    optimizer.check_budget(agent_name="expensive_agent")
except BudgetExceededError as e:
    print(f"Budget exceeded: {e.budget_type} - ${e.current_cost:.2f} >= ${e.budget_limit:.2f}")
```

## Supported Services

### LLM Providers

| Provider | Models | Pricing (per 1M tokens) |
|----------|--------|------------------------|
| Anthropic | Claude Opus/Sonnet/Haiku 4.5 | $1-$75 |
| Google | Gemini 1.5 Flash/Pro | $0.075-$5 |
| Groq | Llama 3.3 70B | $0.59-$0.79 |
| Cerebras | Llama 3.1 8B/70B | $0.10-$0.60 |
| DeepSeek | DeepSeek V3, R1 | $0.20-$2.19 |
| Qwen | Qwen 2.5 72B | $0.35-$0.40 |
| OpenRouter | 50+ models | Varies |

### Voice AI

| Service | Type | Pricing |
|---------|------|---------|
| Cartesia | TTS | $0.042/second |
| ElevenLabs | TTS | $0.30/1K chars |
| Deepgram | STT | $0.0043/minute |
| AssemblyAI | STT | $0.00017/second |

### Infrastructure

| Service | Component | Pricing |
|---------|-----------|---------|
| Supabase | Database | $0.01344/GB-hr |
| Supabase | Edge Functions | $2/1M invocations |
| Vercel | Serverless | $0.18/GB-hr |
| Vercel | Edge | $0.65/1M invocations |
| LangSmith | Traces | $0.00078/trace (Pro) |

## API Reference

### LangGraphCostOptimizer

Main interface for tracking costs.

```python
optimizer = LangGraphCostOptimizer(
    total_budget_usd=100.0,        # Optional: Total budget limit
    per_agent_budget_usd=20.0,     # Optional: Per-agent limit
    per_model_budget_usd=50.0,     # Optional: Per-model limit
    warning_threshold=0.8,          # Warn at 80% of budget
    on_warning=callback_fn,         # Optional: Warning callback
    on_exceeded=callback_fn,        # Optional: Budget exceeded callback
)

# Methods
optimizer.wrap(graph)                  # Wrap LangGraph for auto-tracking
optimizer.get_callback(agent_name)     # Get LangChain callback
optimizer.record_manual(...)           # Manual cost recording
optimizer.check_budget(...)            # Check budget status
optimizer.get_summary()                # Get cost summary
optimizer.reset()                      # Reset all tracking
```

### Pricing Functions

```python
from langgraph_cost_optimizer import (
    calculate_cost,           # LLM cost: calculate_cost("claude-sonnet-4-5", 1000, 500)
    calculate_service_cost,   # Service cost: calculate_service_cost("deepgram/nova-2", 5)
    calculate_audio_tts_cost, # TTS: calculate_audio_tts_cost("cartesia", seconds=30)
    calculate_audio_stt_cost, # STT: calculate_audio_stt_cost("deepgram", minutes=5)
    get_model_pricing,        # Get ModelPricing for a model
    get_service_pricing,      # Get ServicePricing for a service
    get_cheapest_model,       # Find cheapest model matching criteria
    get_all_providers,        # List all providers
)
```

## Use Cases

### Consultant Side Hustle Tracking

Track costs separately for day job vs. personal consulting:

```python
# Day job costs
work_optimizer = LangGraphCostOptimizer(total_budget_usd=500.0)
work_optimizer.record_manual(model_id="claude-sonnet-4-5", ...)

# Side hustle costs
consulting_optimizer = LangGraphCostOptimizer(total_budget_usd=100.0)
consulting_optimizer.record_manual(model_id="deepseek/deepseek-chat", ...)

# Compare monthly spending
print(f"Work: ${work_optimizer.total_cost:.2f}")
print(f"Consulting: ${consulting_optimizer.total_cost:.2f}")
```

### Voice Agent Cost Analysis

```python
# Track a 5-minute voice call
call_duration_min = 5

# STT cost (Deepgram)
stt_cost = calculate_audio_stt_cost("deepgram", minutes=call_duration_min)

# LLM processing (~2000 tokens of dialogue)
llm_cost = calculate_cost("claude-haiku-4-5", input_tokens=2000, output_tokens=1000)

# TTS cost (Cartesia, ~3 min of output)
tts_cost = calculate_audio_tts_cost("cartesia", seconds=180)

total_call_cost = stt_cost + llm_cost + tts_cost
cost_per_minute = total_call_cost / call_duration_min

print(f"Total call cost: ${total_call_cost:.4f}")
print(f"Cost per minute: ${cost_per_minute:.4f}")
```

## Roadmap

- [ ] Subscription tracking (billing dates, renewal alerts)
- [ ] Usage dashboards and reports
- [ ] Multi-account consolidation
- [ ] Cost forecasting
- [ ] Slack/Discord alerts

## License

MIT

## Contributing

Contributions welcome! Please read CONTRIBUTING.md first.
