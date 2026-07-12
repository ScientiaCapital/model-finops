# Model Registry - December 2025

> Comprehensive LLM model IDs and pricing for cost optimization routing.

## Anthropic Claude Models (Direct API)

| Model                     | API Model ID                 | Input $/1M | Output $/1M | Context        |
| ------------------------- | ---------------------------- | ---------- | ----------- | -------------- |
| **Claude Opus 4.5**       | `claude-opus-4-5-20251101`   | $15.00     | $75.00      | 200K           |
| Claude Opus 4.5 (alias)   | `claude-opus-4-5`            | $15.00     | $75.00      | 200K           |
| **Claude Sonnet 4.5**     | `claude-sonnet-4-5-20250929` | $3.00      | $15.00      | 200K (1M beta) |
| Claude Sonnet 4.5 (alias) | `claude-sonnet-4-5`          | $3.00      | $15.00      | 200K           |
| **Claude Haiku 4.5**      | `claude-haiku-4-5-20251001`  | $1.00      | $5.00       | 200K           |
| Claude Haiku 4.5 (alias)  | `claude-haiku-4-5`           | $1.00      | $5.00       | 200K           |
| Claude Opus 4             | `claude-opus-4-20250514`     | $15.00     | $75.00      | 200K           |
| Claude Sonnet 4           | `claude-sonnet-4-20250514`   | $3.00      | $15.00      | 200K           |

**Notes:**

- Use aliases (e.g., `claude-sonnet-4-5`) for development, dated versions for production
- 1M context available via `context-1m-2025-08-07` beta header

**Sources:** [Anthropic Docs](https://platform.claude.com/docs/en/about-claude/models/overview)

---

## OpenRouter Models

### Chinese LLMs (Cost-Effective)

| Model             | OpenRouter ID                     | Input $/1M | Output $/1M | Context |
| ----------------- | --------------------------------- | ---------- | ----------- | ------- |
| **DeepSeek V3**   | `deepseek/deepseek-chat`          | $0.30      | $1.20       | 164K    |
| DeepSeek V3.1     | `deepseek/deepseek-v3.1-terminus` | $0.20      | $0.80       | 131K    |
| DeepSeek V3.2     | `deepseek/deepseek-v3.2`          | $0.27      | $0.40       | 131K    |
| DeepSeek Reasoner | `deepseek/deepseek-r1`            | $0.55      | $2.19       | 64K     |
| **Qwen 2.5 72B**  | `qwen/qwen-2.5-72b-instruct`      | $0.35      | $0.40       | 128K    |
| Qwen Max          | `qwen/qwen-max`                   | $1.60      | $6.40       | 32K     |
| Qwen Plus         | `qwen/qwen-plus`                  | $0.40      | $1.20       | 131K    |
| Qwen Coder 7B     | `qwen/qwen-2.5-coder-7b-instruct` | $0.03      | $0.09       | 33K     |
| ERNIE 4.5 300B    | `baidu/ernie-4.5-300b-a47b`       | $0.22      | $0.88       | 131K    |

**Sources:** [OpenRouter](https://openrouter.ai/models)

### Claude via OpenRouter

| Model             | OpenRouter ID                 | Input $/1M | Output $/1M | Context |
| ----------------- | ----------------------------- | ---------- | ----------- | ------- |
| Claude Haiku 4.5  | `anthropic/claude-haiku-4.5`  | $1.00      | $5.00       | 200K    |
| Claude Sonnet 4.5 | `anthropic/claude-sonnet-4.5` | $3.00      | $15.00      | 200K    |
| Claude Opus 4.5   | `anthropic/claude-opus-4.5`   | $15.00     | $75.00      | 200K    |

---

## Fast Inference Providers

| Model            | Provider | Model ID                  | Input $/1M | Output $/1M | Notes          |
| ---------------- | -------- | ------------------------- | ---------- | ----------- | -------------- |
| Llama 3.3 70B    | Groq     | `llama-3.3-70b-versatile` | $0.59      | $0.79       | Ultra-fast LPU |
| Llama 3.1 8B     | Groq     | `llama-3.1-8b-instant`    | $0.05      | $0.08       | Fastest        |
| Llama 3.1 8B     | Cerebras | `llama3.1-8b`             | $0.10      | $0.10       | 1000+ tok/s    |
| Llama 3.1 70B    | Cerebras | `llama3.1-70b`            | $0.60      | $0.60       | Fast inference |
| Gemini 1.5 Flash | Google   | `gemini-1.5-flash`        | $0.075     | $0.30       | Cheapest       |

---

## Recommended Model Selection by Use Case

```python
MODEL_ROUTING = {
    # Complex reasoning / coding
    "complex": "claude-sonnet-4-5",

    # Fast cheap responses
    "fast_cheap": "claude-haiku-4-5",

    # Bulk processing / scripts (90% savings)
    "bulk": "deepseek/deepseek-chat",

    # Real-time voice (<1s latency)
    "realtime": "llama-3.3-70b-versatile",  # Groq

    # Code generation
    "code": "qwen/qwen-2.5-coder-7b-instruct",

    # Chinese content
    "chinese": "qwen/qwen-2.5-72b-instruct",

    # Budget fallback
    "fallback": "gemini-1.5-flash",
}
```

---

## Cost Comparison Examples

### 1M Token Request Cost

| Model             | Input Cost | Output Cost | Total  |
| ----------------- | ---------- | ----------- | ------ |
| Claude Opus 4.5   | $15.00     | $75.00      | $90.00 |
| Claude Sonnet 4.5 | $3.00      | $15.00      | $18.00 |
| Claude Haiku 4.5  | $1.00      | $5.00       | $6.00  |
| DeepSeek V3       | $0.30      | $1.20       | $1.50  |
| Qwen 2.5 72B      | $0.35      | $0.40       | $0.75  |
| Gemini 1.5 Flash  | $0.075     | $0.30       | $0.375 |

### Potential Savings

Routing bulk processing from Claude Sonnet to DeepSeek V3:

- **Before**: $18.00/1M tokens
- **After**: $1.50/1M tokens
- **Savings**: 92%

---

_Last updated: 2025-12-29_
