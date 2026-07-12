# AI Cost Optimizer - MCP Server

This MCP (Model Context Protocol) server enables Claude Desktop to interact with the AI Cost Optimizer service, providing intelligent LLM routing and cost management directly within your Claude conversations.

## Overview

The MCP server acts as a bridge between Claude Desktop and the AI Cost Optimizer FastAPI service. It exposes 5 powerful tools that Claude can use to:

- Route prompts through cost-optimized models
- Check model pricing across providers
- Get recommendations without executing
- Monitor usage and spending
- Manage budgets and alerts

## Prerequisites

### 1. AI Cost Optimizer Service

The main AI Cost Optimizer service must be running (either locally or deployed to RunPod).

**Local Setup:**

```bash
# From the parent directory
cd ..
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure providers
cp .env.example .env
# Edit .env and add your API keys

# Start service
python main.py
```

Service will run at `http://localhost:8000`

**Cloud Deployment:**
See the main README for RunPod deployment instructions. Update the `COST_OPTIMIZER_API_URL` environment variable to point to your deployed instance.

### 2. Python Environment

- Python 3.10 or higher
- pip or uv package manager

## Installation

### Option 1: Direct Installation

```bash
# Navigate to this directory
cd mcp

# Install dependencies
pip install -r requirements.txt

# Test the server
python server.py
# (Press Ctrl+C to stop - it's waiting for MCP protocol communication)
```

### Option 2: Using UV (Recommended)

```bash
# Install UV if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv pip install -r requirements.txt
```

## Configuration

### Environment Variables

Create a `.env` file or set environment variables:

```bash
# Required: URL of the AI Cost Optimizer service
COST_OPTIMIZER_API_URL=http://localhost:8000

# Optional: API key if authentication is enabled
COST_OPTIMIZER_API_KEY=your-api-key-here
```

**For RunPod deployment:**

```bash
COST_OPTIMIZER_API_URL=https://your-pod-id.runpod.io
```

## Claude Desktop Setup

### Step 1: Locate Config File

Find your Claude Desktop configuration file:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

### Step 2: Add MCP Server Configuration

Edit the config file and add the MCP server:

```json
{
  "mcpServers": {
    "ai-cost-optimizer": {
      "command": "python",
      "args": ["/absolute/path/to/ai-cost-optimizer/mcp/server.py"],
      "env": {
        "COST_OPTIMIZER_API_URL": "http://localhost:8000",
        "COST_OPTIMIZER_API_KEY": ""
      }
    }
  }
}
```

**Using UV:**

```json
{
  "mcpServers": {
    "ai-cost-optimizer": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/ai-cost-optimizer/mcp", "server.py"],
      "env": {
        "COST_OPTIMIZER_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

### Step 3: Restart Claude Desktop

Completely quit and restart Claude Desktop for the changes to take effect.

## Available Tools

Once configured, Claude will have access to these tools:

### 1. `complete_prompt`

Route a prompt through the cost optimizer with automatic model selection.

**Parameters:**

- `prompt` (required): The prompt to complete
- `max_tokens` (optional): Maximum response length (default: 1000)
- `budget_limit` (optional): Maximum cost in USD
- `user_id` (optional): User ID for tracking (default: "default")
- `force_provider` (optional): Force specific provider
- `force_model` (optional): Force specific model

**Example:**

```
Please use the cost optimizer to complete this prompt:
"Explain quantum entanglement in simple terms"
```

### 2. `check_model_costs`

Get pricing for all available models across all providers.

**Example:**

```
Show me all available models and their costs
```

### 3. `get_recommendation`

Analyze prompt complexity and get model recommendation without executing.

**Parameters:**

- `prompt` (required): The prompt to analyze
- `max_tokens` (optional): Expected response length
- `budget_limit` (optional): Budget constraint

**Example:**

```
Analyze this prompt and recommend a model:
"Write a comprehensive research paper on climate change"
```

### 4. `query_usage`

Get usage statistics and spending information.

**Parameters:**

- `user_id` (optional): User ID to query (default: "default")
- `days` (optional): Lookback period (default: 30)

**Example:**

```
What's my AI spending this month?
```

### 5. `set_budget`

Configure monthly budget limits and alert thresholds.

**Parameters:**

- `monthly_limit` (required): Monthly budget in USD
- `user_id` (optional): User ID (default: "default")
- `alert_thresholds` (optional): Alert percentages (default: [0.5, 0.8, 0.9])

**Example:**

```
Set my monthly AI budget to $50 with alerts at 50%, 80%, and 90%
```

## Troubleshooting

### "Cannot connect to AI Cost Optimizer service"

**Solution:** Ensure the FastAPI service is running:

```bash
cd ..
python main.py
```

Verify it's accessible:

```bash
curl http://localhost:8000/
```

### "MCP server not appearing in Claude Desktop"

**Solutions:**

1. Check the config file path is correct
2. Ensure the `server.py` path is absolute, not relative
3. Verify Python is in your PATH
4. Check Claude Desktop logs for errors
5. Restart Claude Desktop completely (quit, not just close window)

### "No providers available"

**Solution:** Configure at least one provider API key in the main service's `.env` file:

```bash
cd ..
nano .env  # or your preferred editor

# Add at least one API key:
GOOGLE_API_KEY=your-key-here
ANTHROPIC_API_KEY=your-key-here
```

Restart the service after updating environment variables.

### "Permission denied" when running server.py

**Solution:** Make the script executable:

```bash
chmod +x server.py
```

## Testing

Test the MCP server manually:

```bash
# The server communicates via stdio, so running it directly will wait for input
python server.py

# To test the API service directly:
curl http://localhost:8000/v1/models
curl -X POST http://localhost:8000/v1/complete \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello world", "max_tokens": 50}'
```

## Architecture

```
┌─────────────────┐
│ Claude Desktop  │
│                 │
│  User asks to   │
│  route prompt   │
└────────┬────────┘
         │ MCP Protocol (stdio)
         ▼
┌─────────────────┐
│  MCP Server     │  (This component)
│  server.py      │
│                 │
│  - Translates   │
│  - Validates    │
│  - Formats      │
└────────┬────────┘
         │ HTTP REST
         ▼
┌─────────────────┐
│  FastAPI        │
│  Service        │
│                 │
│  /v1/complete   │
│  /v1/models     │
│  /v1/usage      │
└────────┬────────┘
         │
         ▼
    [LLM Providers]
```

## Development

### Modifying Tools

To add or modify tools, edit `server.py`:

1. Add tool definition in `list_tools()`
2. Implement handler method (e.g., `_my_new_tool()`)
3. Add case in `call_tool()` dispatcher
4. Update `mcp.json` with tool metadata

### Logging

The server logs to stderr (stdout is reserved for MCP protocol):

```python
print("Debug message", file=sys.stderr)
```

View logs in Claude Desktop's MCP server logs.

## Production Deployment

For production use with RunPod or cloud deployment:

1. Deploy the main FastAPI service to RunPod (see parent README)
2. Update `COST_OPTIMIZER_API_URL` in your Claude Desktop config:
   ```json
   "env": {
     "COST_OPTIMIZER_API_URL": "https://your-pod-id.runpod.io"
   }
   ```
3. Optionally enable API key authentication in the service
4. Restart Claude Desktop

## Support

- **Issues**: https://github.com/yourusername/ai-cost-optimizer/issues
- **Main Documentation**: See parent directory README.md
- **MCP Protocol**: https://modelcontextprotocol.io

## License

MIT License - See LICENSE file in parent directory
