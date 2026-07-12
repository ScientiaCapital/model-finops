# Cost Optimization Agent

> AI Spending Analyst powered by Claude Agent SDK

An intelligent agent that analyzes your AI/LLM usage patterns, identifies cost-saving opportunities, and provides actionable recommendations for optimizing spending.

## Features

### 🔍 **Analysis Tools**

- **Usage Statistics**: Total costs, request counts, provider breakdowns
- **Cost Patterns**: Spending trends, peak usage times, daily analysis
- **Recent Requests**: Query-level analysis for pattern identification

### 💰 **Optimization Tools**

- **Smart Recommendations**: Prioritized opportunities with estimated savings
- **Cache Analysis**: Hit rates, savings tracking, popular queries
- **Provider Comparison**: Cost and quality metrics across providers

### 🎯 **Key Capabilities**

- Natural language queries ("How much did I spend this week?")
- Actionable, data-driven recommendations
- Business-friendly explanations with specific metrics
- Interactive session mode for deep analysis

## Quick Start

### Prerequisites

1. **Python 3.10+** (Check: `python3 --version`)
2. **Anthropic API Key** ([Get one here](https://console.anthropic.com/))
3. **Parent project setup** (AI Cost Optimizer FastAPI service with data)

### Installation

```bash
# Navigate to agent directory
cd agent

# Activate virtual environment (if not already active)
source .venv/bin/activate

# Install dependencies (already done during setup)
pip install -r requirements.txt
```

### Set API Key

```bash
# Set your Anthropic API key
export ANTHROPIC_API_KEY='your-api-key-here'

# Or add to ~/.zshrc or ~/.bashrc for persistence:
echo 'export ANTHROPIC_API_KEY="your-api-key-here"' >> ~/.zshrc
source ~/.zshrc
```

## Usage

### Interactive Session Mode (Recommended)

```bash
python cost_optimizer_agent.py
```

This starts an interactive conversation with the agent:

```
🤖 Cost Optimization Agent (Session Mode)
============================================================
Type 'exit' or 'quit' to end the session

You: How much have I spent this week?
🤖 Agent: Let me analyze your spending for the past week...
[Agent analyzes and responds]

You: Where can I save money?
🤖 Agent: I've identified 3 optimization opportunities...
[Agent provides recommendations]

You: exit
👋 Session ended. Happy optimizing!
```

### Single Query Mode

For one-off questions:

```bash
python cost_optimizer_agent.py "How much did I spend this month?"
python cost_optimizer_agent.py "Analyze my last 100 queries"
python cost_optimizer_agent.py "Compare provider costs"
```

## Example Queries

### Cost Analysis

```
"How much have I spent this week?"
"What's my average cost per request?"
"Show me spending trends for the last 30 days"
"What was my most expensive day?"
```

### Optimization

```
"Where can I save money?"
"Generate cost optimization recommendations"
"What's my biggest cost driver?"
"How can I reduce my Claude costs?"
```

### Cache Analysis

```
"Is my cache working well?"
"How much am I saving with caching?"
"What are my most popular cached queries?"
"What's my cache hit rate?"
```

### Provider Comparison

```
"Compare Gemini vs Claude costs"
"Which provider am I using most?"
"Show me provider performance"
"What's the cost difference between providers?"
```

### Deep Analysis

```
"Analyze my last 100 queries for patterns"
"Find inefficiencies in my recent requests"
"Why are my costs increasing?"
"Review my complexity distribution"
```

## Architecture

### File Structure

```
agent/
├── cost_optimizer_agent.py    # Main agent application
├── tools.py                    # 10 custom analysis tools (6 core + 4 learning)
├── model_abstraction.py        # Black-box tier mapping for competitive protection
├── customer_dashboard.py       # Customer-safe CLI dashboard (tier labels only)
├── admin_dashboard.py          # Internal admin CLI dashboard (shows actual models)
├── requirements.txt            # Python dependencies
├── README.md                   # This file
└── .venv/                      # Virtual environment
```

### Custom Tools

The agent has 10 specialized tools:

#### Core Analysis Tools (6)

1. **`get_usage_stats()`** - Overall usage and cost statistics
2. **`analyze_cost_patterns(days)`** - Spending trends over time
3. **`get_recommendations()`** - Prioritized optimization opportunities
4. **`query_recent_requests(limit)`** - Recent request analysis
5. **`check_cache_effectiveness()`** - Cache performance metrics
6. **`compare_providers()`** - Provider cost/quality comparison

#### Learning Intelligence Tools (4) - Phase 1

7. **`get_smart_recommendation(prompt)`** - AI-powered routing recommendations with confidence levels
8. **`get_pattern_analysis()`** - Learning progress across 6 query patterns
9. **`get_provider_performance(mode, complexity)`** - Model performance rankings (internal/external view)
10. **`calculate_potential_savings(days, complexity)`** - ROI calculator for smart routing

### Agent Capabilities

- **Natural Language Understanding**: Ask questions in plain English
- **Multi-Tool Reasoning**: Combines multiple tools for complex analysis
- **Context Awareness**: Remembers conversation history in session mode
- **Data-Driven**: All recommendations backed by actual usage data
- **Cost-Conscious**: Uses Claude 3.5 Sonnet for optimal quality/cost

## Advanced Usage

### Custom Time Ranges

```bash
python cost_optimizer_agent.py "Analyze cost patterns for the last 14 days"
```

The agent will use `analyze_cost_patterns(days=14)` automatically.

### Targeted Analysis

```bash
python cost_optimizer_agent.py "Analyze my last 50 Claude requests"
```

The agent combines `query_recent_requests(50)` with provider filtering.

### Comprehensive Review

In interactive mode:

```
You: Give me a complete cost audit
Agent: [Uses multiple tools]
  1. Overall stats
  2. Provider comparison
  3. Cache effectiveness
  4. Optimization recommendations
```

## Troubleshooting

### "ANTHROPIC_API_KEY not found"

```bash
# Set the API key
export ANTHROPIC_API_KEY='your-key'

# Verify it's set
echo $ANTHROPIC_API_KEY
```

### "No module named 'app'"

The agent imports from `../app/`. Make sure you're running from the `agent/` directory and the parent project structure is intact.

### "Database not found"

The agent looks for `../optimizer.db`. Make sure:

1. The FastAPI service has been run at least once
2. You have some usage data in the database
3. The database file exists at the project root

### "Virtual environment not activated"

```bash
cd agent
source .venv/bin/activate
```

## Learning Intelligence Tools (Phase 1)

The agent now includes 4 powerful learning-powered tools that analyze historical performance data to provide smart routing recommendations with black-box abstraction for competitive protection.

### 1. get_smart_recommendation

Get AI-powered routing recommendations based on historical performance for similar queries.

**Example Queries:**

```
"What's the best model for debugging Python code?"
"Recommend a model for code review tasks"
"Which tier should I use for API documentation?"
```

**Returns:**

- Recommended tier (e.g., "Economy Tier", "Premium Tier")
- Confidence level (high/medium/low based on sample size)
- Quality score and estimated cost
- Pattern detection (code, analysis, creative, etc.)
- Reasoning based on historical data

**Key Features:**

- Uses black-box abstraction (shows tiers, not models)
- Confidence levels based on sample count (high: 10+ samples, medium: 5-9, low: <5)
- Analyzes 6 query patterns: code, analysis, creative, explanation, factual, reasoning

### 2. get_pattern_analysis

View learning progress and maturity across all 6 query patterns.

**Example Queries:**

```
"Show me learning progress by pattern"
"Which patterns have high confidence?"
"How much training data do we have per pattern?"
```

**Returns:**

- Sample count per pattern
- Confidence level (high/medium/low)
- Best performing tier for each pattern
- Samples needed to reach high confidence

**Use Cases:**

- Identify which patterns need more training data
- Understand learning system maturity
- Track progress over time

### 3. get_provider_performance

Compare model performance across quality and cost metrics.

**Example Queries:**

```
"Compare provider performance"
"Show model rankings for code tasks"
"What's the best tier for simple queries?"
```

**Parameters:**

- `mode`: "internal" (shows actual models - admin only) or "external" (shows tier labels - default)
- `complexity`: Filter by "simple" or "complex" queries

**Returns:**

- Performance rankings by composite score
- Quality score (0-1 based on feedback)
- Average cost per request
- Request count (sample size)

**Composite Score Formula:**

```
score = (quality * 0.5) + (cost_efficiency * 0.3) + (volume * 0.2)
```

### 4. calculate_potential_savings

Calculate ROI of learning-powered routing vs current usage.

**Example Queries:**

```
"How much could I save with smart routing?"
"Calculate potential savings for last 30 days"
"What's the ROI of optimization for code queries?"
```

**Parameters:**

- `days`: Number of days to analyze (default: 30)
- `complexity`: Filter by "simple" or "complex" queries

**Returns:**

- Current usage cost and request count
- Optimized routing cost (using best cost-effective model)
- Potential savings ($ and %)
- Annualized savings projection
- Quality impact assessment

**Example Output:**

```
Current Monthly Cost:    $2.45
Optimized Monthly Cost:  $0.87
────────────────────────────────
Potential Savings:       $1.58 (64.5% reduction)
Annualized Savings:      $18.96/year

Using: Economy Tier (Quality: 0.85)
```

## CLI Dashboards

Two CLI dashboard versions provide visual learning intelligence:

### Customer Dashboard (customer_dashboard.py)

**SAFE FOR EXTERNAL DISTRIBUTION** - Shows only tier labels, never exposes actual model names.

```bash
python customer_dashboard.py
```

**Features:**

- Training data overview (total queries, models, feedback)
- Pattern distribution with progress bars
- Top performing tiers (black-boxed)
- 30-day savings projection
- Learning progress by pattern

**Security:**

- ONLY shows tier labels (Economy, Premium, Standard, Specialty)
- NO model names exposed
- NO admin view option

### Admin Dashboard (admin_dashboard.py)

**INTERNAL USE ONLY - NEVER DISTRIBUTE TO CUSTOMERS** - Shows actual model names and internal routing logic.

```bash
# Internal view (shows actual models)
python admin_dashboard.py --mode internal

# External view (shows tiers - same as customer dashboard)
python admin_dashboard.py --mode external
```

**Features:**

- Same visualizations as customer dashboard
- Internal mode reveals actual model names (e.g., "openrouter/deepseek-coder")
- For development and internal analysis only

**Security Warning:**

- Contains competitive intelligence (model selection strategy)
- Exposes cost optimization approach
- NEVER share with customers or external parties

### Model Abstraction Layer

The system uses a two-tier architecture for competitive protection:

**Internal View (Admin Only):**

- Full model names: "openrouter/deepseek-coder", "claude/claude-3-haiku", etc.
- Used for development, debugging, and internal analysis
- Contains competitive intelligence

**External View (Customer-Facing):**

- Tier labels: "Economy Tier", "Premium Tier", "Standard Tier", "Specialty Tier"
- Protects which specific models/providers are used
- Delivers value without exposing strategy

**Why This Matters:**

- Prevents competitors from copying your model selection strategy
- Protects hard-won knowledge about which models work best for each task
- Maintains competitive advantage while delivering customer value

**File Mapping:**

- `model_abstraction.py` - Tier mapping logic
- `customer_dashboard.py` - External view only, customer-safe
- `admin_dashboard.py` - Both views, internal use only
- Tools with `mode` parameter - Respects view separation

## Tips for Best Results

1. **Use Session Mode** for exploratory analysis
2. **Be Specific** in your questions for better responses
3. **Request Comparisons** to understand trade-offs
4. **Ask for Recommendations** regularly to stay optimized
5. **Provide Context** (e.g., "last week", "high-cost queries")
6. **Use Learning Tools** to leverage historical performance data
7. **Check Pattern Analysis** to understand learning maturity

## Performance

- **Response Time**: 2-10 seconds depending on query complexity
- **Tool Calls**: Agent may use 1-3 tools per query
- **Cost**: ~$0.001-0.01 per query (uses Claude 3.5 Sonnet)
- **Data Access**: Direct SQLite queries for fast analysis

## Next Steps

### Integrate with Your Workflow

```python
# Use in your own Python scripts
from cost_optimizer_agent import run_agent

# Single query
await run_agent("What's my total spend?")

# Session
await run_agent("Let's analyze", session_mode=True)
```

### Scheduled Reports

Create a cron job for daily/weekly cost reports:

```bash
# Daily cost report at 9 AM
0 9 * * * cd /path/to/agent && python cost_optimizer_agent.py "Generate daily cost report" >> reports.log
```

### API Integration

Build a web interface that calls the agent for cost dashboards.

## Support

For issues related to:

- **Agent functionality**: Check this README and tool implementations
- **Claude Agent SDK**: https://docs.claude.com/en/api/agent-sdk/python
- **AI Cost Optimizer**: See parent project README

## What's Next?

Consider these enhancements:

- 📊 **Export reports** to PDF/CSV
- 📧 **Email alerts** for budget thresholds
- 📈 **Visualization** with charts and graphs
- 🔄 **Auto-optimization** that updates routing rules
- 👥 **Multi-user** analysis for team usage

---

**Built with Claude Agent SDK v0.1.6**

Need help? Run the agent and ask: "What can you help me with?"
