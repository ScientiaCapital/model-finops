# AI Cost Optimizer

> **Intelligent LLM router that reduces AI API costs by up to 60%** without sacrificing quality.

## What It Does

Automatically routes your prompts to the most cost-efficient model for each task:

- **Smart routing** analyzes each prompt and selects the optimal provider
- **Cost tracking** monitors spending across all requests
- **Multi-provider support** works with Google Gemini, Anthropic Claude, OpenRouter, and more
- **MCP integration** seamlessly integrates with Claude Desktop

**No configuration needed** - just add your API keys and let the optimizer do the rest.

## Quick Start

### 1. Get API Keys

You need at least **one** of these:

- **Google Gemini** (recommended - free tier): https://aistudio.google.com/app/apikey
- **Anthropic Claude**: https://console.anthropic.com/
- **OpenRouter** (all models): https://openrouter.ai/keys

### 2. Setup

```bash
# Clone or navigate to project
cd ai-cost-optimizer

# Copy environment template
cp .env.example .env

# Edit .env and add your API key(s)
nano .env

# Install dependencies
pip install -r requirements.txt
```

### 3. Start the Service

```bash
# Run the optimizer
python app/main.py

# You should see:
# "AI Cost Optimizer initialized with providers: ['gemini']"
# "Uvicorn running on http://0.0.0.0:8000"
```

Keep this terminal running!

### 4. Configure Claude Desktop (Optional)

Edit your Claude Desktop config:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

Add the MCP server:

```json
{
  "mcpServers": {
    "ai-cost-optimizer": {
      "command": "python3",
      "args": ["/ABSOLUTE/PATH/TO/ai-cost-optimizer/mcp/server.py"],
      "env": {
        "COST_OPTIMIZER_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

**Important**: Use the absolute path to `mcp/server.py` on your system!

### 5. Test It!

#### Via API

```bash
curl -X POST http://localhost:8000/complete \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is quantum computing?", "max_tokens": 1000}'
```

Response:

```json
{
  "response": "Quantum computing is...",
  "provider": "gemini",
  "model": "gemini-1.5-flash",
  "tokens_in": 4,
  "tokens_out": 50,
  "cost": 0.000015,
  "total_cost_today": 0.000015
}
```

#### Via Claude Desktop

```
Please use the cost optimizer to answer: What is quantum computing?
```

You should see the response along with cost tracking.

## API Endpoints

### Complete a Prompt

```bash
POST /complete
{
  "prompt": "Your prompt here",
  "max_tokens": 1000
}
```

Returns the response with cost breakdown.

### Get Usage Statistics

```bash
GET /stats
```

Returns total cost and request statistics.

### Get Provider Status

```bash
GET /providers
```

Lists all available providers and their status.

### Health Check

```bash
GET /health
```

Returns service health status.

## Environment Variables

Create a `.env` file with your API keys:

```bash
# Provider API keys (add at least one)
GOOGLE_API_KEY=your-key-here
ANTHROPIC_API_KEY=your-key-here
OPENROUTER_API_KEY=your-key-here
CEREBRAS_API_KEY=your-key-here

# Optional configuration
PORT=8000
LOG_LEVEL=INFO
```

## How It Works

The optimizer uses an **intelligent routing engine** that:

1. Analyzes incoming prompts
2. Selects the most cost-efficient provider for the task
3. Tracks all costs and usage metrics
4. Automatically falls back to alternative providers if needed

**Result**: Up to 60% cost reduction compared to always using premium models.

## Troubleshooting

### Service won't start

```bash
# Check if port 8000 is in use
lsof -i :8000

# Verify API keys are set
cat .env
```

### MCP tool not appearing in Claude Desktop

1. Verify absolute path in `claude_desktop_config.json`
2. Check service is running: `curl http://localhost:8000/health`
3. Completely quit and restart Claude Desktop (Cmd+Q on Mac)
4. Check Claude Desktop logs

### API errors

- Verify API keys are valid and active
- Check provider service status
- Review logs for detailed error messages

## Testing

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run test suite
pytest

# Run with coverage
pytest --cov=app tests/
```

## License

MIT - do whatever you want with it!

## Questions?

This is a learning project built to help developers reduce AI costs. Feel free to fork, modify, and make it yours!
