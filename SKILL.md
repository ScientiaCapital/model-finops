---
name: "ai-cost-optimizer"
description: "Save 40-70% on AI costs with intelligent multi-LLM routing. Automatically selects the optimal model based on task complexity across 40+ models from 8 providers."
license: "MIT"
---

# AI Cost Optimizer

## 🎯 Overview

**Stop overspending on AI.** The AI Cost Optimizer automatically routes your prompts to the most cost-efficient model based on task complexity, saving 40-70% on API costs while maintaining quality.

### Why This Matters

- **Developer Pain**: AI costs can escalate from $50 to $5,000/month without warning
- **Current Problem**: Manual model selection is tedious and error-prone
- **Our Solution**: Intelligent routing that uses GPT-4 only when necessary, free models when possible

### Key Features

✅ **Smart Routing**: Automatically analyzes prompt complexity (0.0-1.0 score) and selects optimal model
✅ **Multi-Provider**: Access 40+ models from Anthropic, Google, Cerebras, DeepSeek, OpenRouter, and more
✅ **Cost Tracking**: Real-time monitoring with per-request cost breakdown
✅ **Budget Management**: Set limits and receive alerts at 50%, 80%, 90% thresholds
✅ **Transparent Pricing**: See exact costs before and after each request
✅ **Zero Lock-in**: Works with your existing API keys, no proprietary wrappers

## 📋 Prerequisites

### 1. Deploy AI Cost Optimizer Service

The FastAPI service must be running (locally or on RunPod).

**Quick Start (Local)**:
```bash
# Clone repository
git clone https://github.com/yourusername/ai-cost-optimizer.git
cd ai-cost-optimizer

# Setup environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure providers
cp .env.example .env
# Edit .env and add at least one API key

# Start service
python app/main.py
```

Service runs at `http://localhost:8000`

**RunPod Deployment** (Recommended for production):
See [Deployment Guide](https://github.com/yourusername/ai-cost-optimizer/blob/main/DEPLOYMENT.md)

### 2. API Keys (Choose At Least One)

- **Free Option**: Google Gemini (no API key cost, 1M free requests/month)
- **Anthropic**: Claude models ($3-15/M tokens)
- **Cerebras**: Ultra-fast Llama ($0.10-0.60/M tokens)
- **DeepSeek**: Chinese LLM specialist ($0.14-0.28/M tokens)
- **OpenRouter**: Gateway to 100+ models
- **HuggingFace**: Open source models

## 🚀 Installation

### Step 1: Install the Skill

Install from Claude Desktop Skills Marketplace or download the .zip package.

### Step 2: Configure MCP Server

Add to your Claude Desktop config:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
**Linux**: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "ai-cost-optimizer": {
      "command": "python",
      "args": [
        "/absolute/path/to/ai-cost-optimizer/mcp/server.py"
      ],
      "env": {
        "COST_OPTIMIZER_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

**For RunPod deployment**, update the URL:
```json
"COST_OPTIMIZER_API_URL": "https://your-pod-id.runpod.io"
```

### Step 3: Restart Claude Desktop

Completely quit and restart Claude Desktop.

## 💡 Usage

Once installed, Claude has access to 5 powerful tools:

### 1. Complete Prompt with Smart Routing

**Command**: Ask Claude to route your prompt through the optimizer

**Example**:
```
Please use the cost optimizer to answer: "What is quantum entanglement?"
```

**Response**:
```
Response: Quantum entanglement is a phenomenon where...

Cost Analysis:
• Provider: google
• Model: gemini-2.0-flash-exp
• Cost: $0.000000 (FREE!)
• Complexity Score: 0.25
• Tokens: 12 input / 87 output

💰 Saved ~$0.002 vs GPT-4
```

### 2. Check Model Costs

**Command**: View all available models and pricing

**Example**:
```
Show me all available models and their costs
```

**Response**:
```
# Available Models and Pricing

## GOOGLE
**gemini-2.0-flash-exp**
• Input: $0.00 per 1M tokens
• Output: $0.00 per 1M tokens
• Context Window: 1,000,000 tokens

**gemini-1.5-pro**
• Input: $1.25 per 1M tokens
• Output: $5.00 per 1M tokens
• Context Window: 2,000,000 tokens

## ANTHROPIC
**claude-3-5-sonnet**
• Input: $3.00 per 1M tokens
• Output: $15.00 per 1M tokens
• Context Window: 200,000 tokens

[... full model list ...]

Total Models Available: 24
```

### 3. Get Recommendation Without Executing

**Command**: Analyze complexity and get cost estimate before running

**Example**:
```
Analyze this prompt and recommend a model:
"Write a comprehensive technical architecture document for a distributed system"
```

**Response**:
```
Recommendation Analysis

Complexity Assessment:
• Complexity Score: 0.82
• Tier: Premium

Recommended Model:
• Provider: anthropic
• Model: claude-3-5-sonnet
• Estimated Cost: $0.045

Reasoning:
High complexity - using premium model for best quality

Token Estimate:
• Input: ~85 tokens
• Expected Output: 4000 tokens max

Note: This is an estimate. Use complete_prompt to execute.
```

### 4. Query Usage Statistics

**Command**: Monitor your spending and usage

**Example**:
```
What's my AI spending this month?
```

**Response**:
```
Usage Statistics (30 days)

Overview:
• Total Cost: $12.45
• Total Requests: 156
• Remaining Budget: $37.55
• Budget Utilization: 24.9%

Models Used:
• gemini-1.5-flash: 120 requests
• claude-3-5-sonnet: 24 requests
• deepseek-chat: 12 requests
```

### 5. Set Budget

**Command**: Configure spending limits and alerts

**Example**:
```
Set my monthly AI budget to $50 with alerts at 50%, 80%, and 90%
```

**Response**:
```
Budget Updated Successfully

• User: default
• Monthly Limit: $50.00
• Alert Thresholds: 50%, 80%, 90%

You will receive alerts when spending reaches these thresholds.
```

## 🎨 Cost Tiers

The optimizer automatically categorizes prompts into tiers:

| Tier | Complexity | Example Tasks | Models | Cost/M Tokens |
|------|------------|---------------|--------|---------------|
| **Free** | 0.0-0.2 | Simple facts, definitions, basic Q&A | Gemini 2.0 Flash | $0 |
| **Cheap** | 0.2-0.4 | Code snippets, summaries, translations | Cerebras, DeepSeek, Haiku | $0.1-1 |
| **Medium** | 0.4-0.7 | Analysis, complex explanations, refactoring | Gemini Pro, Sonnet | $1-5 |
| **Premium** | 0.7-1.0 | Architecture design, research papers, complex code | Opus, GPT-4 | $5-75 |

## 📊 Real-World Savings Examples

### Example 1: Daily Q&A (100 requests/day)

**Without Optimizer**:
- All requests to GPT-4
- Cost: ~$150/month

**With Optimizer**:
- 80% routed to free/cheap models
- 20% to premium models
- Cost: ~$30/month
- **Savings: $120/month (80%)**

### Example 2: Code Assistant (50 requests/day)

**Without Optimizer**:
- All requests to Claude Sonnet
- Cost: ~$90/month

**With Optimizer**:
- Simple syntax: Free models
- Complex architecture: Premium models
- Cost: ~$35/month
- **Savings: $55/month (61%)**

### Example 3: Content Writing (200 requests/day)

**Without Optimizer**:
- Mix of GPT-3.5 and GPT-4
- Cost: ~$200/month

**With Optimizer**:
- Intelligent routing by complexity
- Cost: ~$60/month
- **Savings: $140/month (70%)**

## ⚙️ Configuration

### Environment Variables (Service)

Configure in the AI Cost Optimizer service `.env`:

```bash
# Provider API Keys (configure at least one)
GOOGLE_API_KEY=your-key-here
ANTHROPIC_API_KEY=sk-ant-...
CEREBRAS_API_KEY=...
DEEPSEEK_API_KEY=...
OPENROUTER_API_KEY=sk-or-v1-...

# Budget
DEFAULT_MONTHLY_BUDGET=100.00

# Database (automatic in Docker)
DATABASE_URL=sqlite:///./optimizer.db
```

### MCP Server Configuration

Adjust in `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ai-cost-optimizer": {
      "env": {
        "COST_OPTIMIZER_API_URL": "http://localhost:8000",
        "COST_OPTIMIZER_API_KEY": ""
      }
    }
  }
}
```

## 🔧 Troubleshooting

### Issue: "Cannot connect to AI Cost Optimizer service"

**Solution**: Ensure the service is running:
```bash
cd ai-cost-optimizer
python main.py
```

Verify at: `http://localhost:8000/health`

### Issue: "No providers available"

**Solution**: Add at least one API key to `.env`:
```bash
GOOGLE_API_KEY=your-key-here
```

Restart the service.

### Issue: MCP server not appearing in Claude Desktop

**Solutions**:
1. Use absolute paths, not relative
2. Verify Python is in PATH
3. Check Claude Desktop logs
4. Restart Claude Desktop completely

### Issue: "Budget exceeded"

**Solution**: Increase budget or check usage:
```bash
curl http://localhost:8000/v1/usage
```

Or ask Claude: "What's my current AI spending?"

## 🚢 Deployment to RunPod

For production deployment:

1. **Build Docker Image**:
```bash
docker build -t ai-cost-optimizer:latest .
docker tag ai-cost-optimizer:latest your-dockerhub-username/ai-cost-optimizer:latest
docker push your-dockerhub-username/ai-cost-optimizer:latest
```

2. **Deploy on RunPod**:
- Go to https://www.runpod.io/
- Deploy Custom Container
- Use your Docker image
- Configure environment variables (API keys)
- Add 5GB persistent volume at `/data`

3. **Update Claude Desktop Config**:
```json
"COST_OPTIMIZER_API_URL": "https://your-pod-id.runpod.io"
```

See [full deployment guide](https://github.com/yourusername/ai-cost-optimizer/blob/main/DEPLOYMENT.md).

## 🎯 Advanced Usage

### Force Specific Provider

```
Use Claude Opus specifically for this complex analysis:
[your prompt]
```

The tool will respect your override while still tracking costs.

### Per-Request Budget Limits

```
Complete this with a maximum budget of $0.01:
[your prompt]
```

### Multiple Users

Track spending per user by setting user_id in requests.

## 📚 Resources

- **GitHub**: https://github.com/yourusername/ai-cost-optimizer
- **Documentation**: Full README and API docs
- **Issues**: Bug reports and feature requests
- **Deployment Guide**: RunPod and Railway instructions

## 🤝 Contributing

Contributions welcome! Areas of interest:
- Additional provider integrations
- Improved complexity analysis algorithms
- Cost prediction models
- UI dashboard (Streamlit/React)

## 📄 License

MIT License - Free for personal and commercial use

## 🔮 Roadmap

**v1.1** (Next Month):
- [ ] Streamlit dashboard for usage analytics
- [ ] Cost prediction before execution
- [ ] Provider health checking and failover

**v1.2** (Q2):
- [ ] Advanced routing with ML-based complexity analysis
- [ ] Team collaboration features
- [ ] Webhook alerts for budget thresholds

**v2.0** (Q3):
- [ ] Response quality scoring
- [ ] A/B testing across models
- [ ] Cost vs quality optimization curves

## 💬 Community

Join our community:
- Discord: [Your Discord Server]
- Twitter: [@ai_cost_optimizer]
- LinkedIn: [Your Profile]

## 🙏 Acknowledgments

Built with:
- FastAPI for the API backend
- MCP SDK for Claude Desktop integration
- Anthropic, Google, Cerebras, and other LLM providers

Special thanks to the AI developer community for feedback and testing!

---

**Save money. Ship faster. Let AI routing handle the complexity.**

Install now and start optimizing your AI costs! 🚀
