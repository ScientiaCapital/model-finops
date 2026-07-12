# Cost Optimization Agent - Quick Start

## ✅ Setup Complete!

Your Cost Optimization Agent is fully installed and ready to use. Here's how to get started:

## 1. Set Your API Key

```bash
# Make sure you're in the project root
cd /Users/tmkipper/Desktop/tk_projects/ai-cost-optimizer

# Load your environment variables (includes ANTHROPIC_API_KEY)
source .env

# OR set it directly:
export ANTHROPIC_API_KEY='your-api-key-here'
```

## 2. Navigate to Agent Directory

```bash
cd agent
```

## 3. Activate Virtual Environment

```bash
source .venv/bin/activate
```

## 4. Run the Agent!

### Interactive Mode (Recommended for first time)

```bash
python3 cost_optimizer_agent.py
```

This starts an interactive conversation where you can ask multiple questions:

```
🤖 Cost Optimization Agent (Session Mode)
============================================================
Type 'exit' or 'quit' to end the session

You: What are my total costs?
🤖 Agent: [analyzes and responds]

You: Where can I save money?
🤖 Agent: [provides recommendations]

You: exit
👋 Session ended. Happy optimizing!
```

### Single Query Mode

For one-off questions:

```bash
python3 cost_optimizer_agent.py "What are my total costs?"
python3 cost_optimizer_agent.py "Analyze my last 50 queries"
python3 cost_optimizer_agent.py "Compare provider costs"
```

## 5. Example Queries to Try

### Cost Analysis

- "What are my total costs?"
- "How much did I spend this week?"
- "Show me spending trends"
- "What was my most expensive day?"

### Optimization

- "Where can I save money?"
- "Give me cost optimization recommendations"
- "Why are my costs high?"

### Cache Analysis

- "Is my cache working well?"
- "How much am I saving with caching?"
- "What's my cache hit rate?"

### Provider Comparison

- "Compare Gemini vs Claude costs"
- "Which provider am I using most?"
- "Show me provider performance"

## 6. Test Data

The database has been initialized with sample data:

- 5 test requests
- Mix of simple and complex queries
- Gemini and Claude providers
- Total cost: $0.002298

## Troubleshooting

### "ANTHROPIC_API_KEY not found"

```bash
# Check if it's set
echo $ANTHROPIC_API_KEY

# If empty, load from .env
source ../.env

# Or set directly
export ANTHROPIC_API_KEY='your-key'
```

### "No module named 'claude_agent_sdk'"

Make sure you're in the agent directory and virtual environment is activated:

```bash
cd agent
source .venv/bin/activate
```

### "Database not found"

The init script should have created test data. If not:

```bash
cd ..
python3 init_test_data.py
cd agent
```

## What's Next?

1. **Try it out**: Run the agent and ask questions
2. **Add real data**: Use your FastAPI service to generate actual usage data
3. **Explore features**: Try all 6 tools (stats, patterns, recommendations, etc.)
4. **Go to market planning**: When ready, we can discuss commercialization strategies!

## One-Command Start

```bash
cd /Users/tmkipper/Desktop/tk_projects/ai-cost-optimizer/agent && source .venv/bin/activate && source ../.env && python3 cost_optimizer_agent.py
```

---

**Need Help?** Check the full README.md in this directory or ask me!
