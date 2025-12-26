#!/usr/bin/env python3
"""
MCP Server for AI Cost Optimizer - Claude Desktop Integration.

This MCP (Model Context Protocol) server provides tools for:
- Routing prompts to optimal LLMs based on complexity
- Viewing cost analytics and usage statistics
- Managing the semantic cache

The server communicates with the FastAPI backend to perform operations.
Configure the API URL via COST_OPTIMIZER_API_URL environment variable.

Usage:
    1. Add to Claude Desktop config (claude_desktop_config.json):
       {
         "mcpServers": {
           "ai-cost-optimizer": {
             "command": "python",
             "args": ["/path/to/mcp/server.py"],
             "env": {
               "COST_OPTIMIZER_API_URL": "http://localhost:8000"
             }
           }
         }
       }

    2. Restart Claude Desktop
    3. Use tools via Claude: "Use complete_prompt to answer: What is Python?"
"""
import os
import json
import asyncio
import logging
from typing import Any, Optional
import httpx
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp import types

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
API_BASE_URL = os.getenv("COST_OPTIMIZER_API_URL", "http://localhost:8000")
REQUEST_TIMEOUT = float(os.getenv("MCP_REQUEST_TIMEOUT", "120.0"))

# Initialize MCP server
server = Server("ai-cost-optimizer")


# ============================================================================
# TOOL DEFINITIONS
# ============================================================================

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """
    List available tools for the AI Cost Optimizer.

    Tools:
    - complete_prompt: Route and complete prompts with cost optimization
    - get_cost_summary: View total costs and usage breakdown
    - get_cache_stats: View semantic cache statistics
    - analyze_prompt: Analyze prompt complexity without executing
    """
    return [
        types.Tool(
            name="complete_prompt",
            description=(
                "Route and complete a prompt using the optimal LLM based on complexity. "
                "Automatically selects between Gemini Flash (simple queries) and Claude Haiku (complex queries). "
                "Uses semantic caching to return instant responses for similar previously-asked questions. "
                "Returns response with cost breakdown and usage statistics."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The prompt to complete"
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Maximum tokens in response (default: 1000)",
                        "default": 1000
                    },
                    "force_provider": {
                        "type": "string",
                        "description": "Force a specific provider (optional): gemini, claude, openrouter",
                        "enum": ["gemini", "claude", "openrouter"]
                    }
                },
                "required": ["prompt"]
            }
        ),
        types.Tool(
            name="get_cost_summary",
            description=(
                "Get a summary of API costs and usage. Shows total cost, requests by provider, "
                "and cost breakdown by complexity level. Useful for monitoring spending."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Number of days to look back (default: 7)",
                        "default": 7
                    }
                },
                "required": []
            }
        ),
        types.Tool(
            name="get_cache_stats",
            description=(
                "Get semantic cache statistics. Shows cache hit rate, total entries, "
                "quality scores, and storage used. The semantic cache reduces costs by "
                "returning cached responses for similar prompts."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        types.Tool(
            name="analyze_prompt",
            description=(
                "Analyze a prompt's complexity without executing it. Returns the complexity "
                "classification (simple/complex), detected keywords, token count, and which "
                "provider would be selected. Useful for understanding routing decisions."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The prompt to analyze"
                    }
                },
                "required": ["prompt"]
            }
        ),
        types.Tool(
            name="get_cache_analytics",
            description=(
                "Get comprehensive cache analytics for the cost optimization dashboard. "
                "Shows per-provider breakdown of cache performance including hit rates, "
                "quality scores, and estimated savings. Includes AI-generated recommendations "
                "for optimization. Use this for deep analysis of caching effectiveness."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Number of days to analyze (default: 7)",
                        "default": 7
                    }
                },
                "required": []
            }
        ),
        types.Tool(
            name="get_optimization_score",
            description=(
                "Get the overall optimization score (0-100) and detailed cost analytics. "
                "The score combines cache efficiency, cost reduction percentage, and response "
                "quality into a single metric. Use this to track ROI of the cost optimizer. "
                "Also includes breakdown of costs by provider and complexity level."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Number of days to analyze (default: 7)",
                        "default": 7
                    }
                },
                "required": []
            }
        )
    ]


# ============================================================================
# TOOL HANDLERS
# ============================================================================

@server.call_tool()
async def handle_call_tool(
    name: str,
    arguments: dict[str, Any]
) -> list[types.TextContent]:
    """
    Handle tool execution requests.

    Dispatches to the appropriate handler based on tool name.

    Args:
        name: Tool name to execute
        arguments: Tool arguments

    Returns:
        Tool execution result as TextContent
    """
    handlers = {
        "complete_prompt": handle_complete_prompt,
        "get_cost_summary": handle_get_cost_summary,
        "get_cache_stats": handle_get_cache_stats,
        "analyze_prompt": handle_analyze_prompt,
        "get_cache_analytics": handle_get_cache_analytics,
        "get_optimization_score": handle_get_optimization_score,
    }

    handler = handlers.get(name)
    if not handler:
        raise ValueError(f"Unknown tool: {name}")

    return await handler(arguments)


async def handle_complete_prompt(arguments: dict[str, Any]) -> list[types.TextContent]:
    """
    Handle the complete_prompt tool.

    Routes a prompt to the optimal LLM and returns the response with cost breakdown.
    """
    prompt = arguments.get("prompt")
    max_tokens = arguments.get("max_tokens", 1000)
    force_provider = arguments.get("force_provider")

    if not prompt:
        raise ValueError("Prompt is required")

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            payload = {
                "prompt": prompt,
                "max_tokens": max_tokens
            }

            if force_provider:
                payload["force_provider"] = force_provider

            response = await client.post(
                f"{API_BASE_URL}/complete",
                json=payload
            )

            if response.status_code == 503:
                error_detail = response.json().get("detail", "Service unavailable")
                return [_error_response("Service Unavailable", error_detail)]

            response.raise_for_status()
            data = response.json()

            # Format response with cost breakdown
            complexity_meta = data.get("complexity_metadata", {})
            cache_hit = data.get("cache_hit", False)

            result = f"**Response:**\n\n{data['response']}\n\n---\n\n"

            if cache_hit:
                result += "**[CACHE HIT]** Response retrieved from semantic cache!\n\n"

            result += "**Cost Analysis:**\n"
            result += f"- Provider: {data['provider']}\n"
            result += f"- Model: {data['model']}\n"

            if complexity_meta:
                result += f"- Complexity: {data.get('complexity', 'unknown')} "
                result += f"({complexity_meta.get('token_count', 0)} tokens"

                keywords = complexity_meta.get('keywords_found', [])
                if keywords:
                    result += f", keywords: {', '.join(keywords[:3])}"
                result += ")\n"

            result += f"- Tokens: {data.get('tokens_in', 0)} in / {data.get('tokens_out', 0)} out\n"
            result += f"- Cost: ${data.get('cost', 0):.6f}\n"
            result += f"- Total cost (all time): ${data.get('total_cost_today', 0):.2f}\n"

            return [types.TextContent(type="text", text=result)]

    except httpx.ConnectError:
        return [_connection_error_response()]
    except httpx.HTTPError as e:
        return [_error_response("API Error", str(e))]
    except Exception as e:
        logger.exception("Unexpected error in complete_prompt")
        return [_error_response("Unexpected Error", str(e))]


async def handle_get_cost_summary(arguments: dict[str, Any]) -> list[types.TextContent]:
    """
    Handle the get_cost_summary tool.

    Retrieves cost statistics and usage breakdown from the API.
    """
    days = arguments.get("days", 7)

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(
                f"{API_BASE_URL}/costs/summary",
                params={"days": days}
            )
            response.raise_for_status()
            data = response.json()

            result = f"**Cost Summary (Last {days} Days)**\n\n"

            # Overall stats
            overall = data.get("overall", {})
            result += "**Overall:**\n"
            result += f"- Total Requests: {overall.get('total_requests', 0)}\n"
            result += f"- Total Cost: ${overall.get('total_cost', 0):.4f}\n"
            result += f"- Avg Cost/Request: ${overall.get('avg_cost_per_request', 0):.6f}\n"
            result += f"- Total Tokens In: {overall.get('total_tokens_in', 0):,}\n"
            result += f"- Total Tokens Out: {overall.get('total_tokens_out', 0):,}\n\n"

            # By provider
            by_provider = data.get("by_provider", [])
            if by_provider:
                result += "**By Provider:**\n"
                for p in by_provider:
                    result += f"- {p['provider']}: {p['request_count']} requests, ${p['total_cost']:.4f}\n"
                result += "\n"

            # By complexity
            by_complexity = data.get("by_complexity", [])
            if by_complexity:
                result += "**By Complexity:**\n"
                for c in by_complexity:
                    result += f"- {c['complexity']}: {c['request_count']} requests, ${c['total_cost']:.4f}\n"

            return [types.TextContent(type="text", text=result)]

    except httpx.ConnectError:
        return [_connection_error_response()]
    except httpx.HTTPError as e:
        return [_error_response("API Error", str(e))]
    except Exception as e:
        logger.exception("Unexpected error in get_cost_summary")
        return [_error_response("Unexpected Error", str(e))]


async def handle_get_cache_stats(arguments: dict[str, Any]) -> list[types.TextContent]:
    """
    Handle the get_cache_stats tool.

    Retrieves semantic cache statistics from the API.
    """
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(f"{API_BASE_URL}/cache/stats")
            response.raise_for_status()
            data = response.json()

            result = "**Semantic Cache Statistics**\n\n"

            result += f"- Total Entries: {data.get('total_entries', 0)}\n"
            result += f"- Total Hits: {data.get('total_hits', 0)}\n"

            # Calculate hit rate
            entries = data.get('total_entries', 0)
            hits = data.get('total_hits', 0)
            if entries > 0:
                hit_rate = (hits / entries) * 100
                result += f"- Hit Rate: {hit_rate:.1f}%\n"

            avg_quality = data.get('avg_quality_score', 0)
            if avg_quality:
                result += f"- Avg Quality Score: {avg_quality:.2f}\n"

            cache_size = data.get('cache_size_bytes', 0)
            if cache_size > 0:
                size_kb = cache_size / 1024
                size_mb = size_kb / 1024
                if size_mb >= 1:
                    result += f"- Cache Size: {size_mb:.2f} MB\n"
                else:
                    result += f"- Cache Size: {size_kb:.2f} KB\n"

            result += "\n**How Semantic Caching Works:**\n"
            result += "The cache stores embeddings of previous prompts. When a new prompt "
            result += "is similar (>95% cosine similarity) to a cached prompt, the cached "
            result += "response is returned instantly, saving API costs and latency."

            return [types.TextContent(type="text", text=result)]

    except httpx.ConnectError:
        return [_connection_error_response()]
    except httpx.HTTPError as e:
        return [_error_response("API Error", str(e))]
    except Exception as e:
        logger.exception("Unexpected error in get_cache_stats")
        return [_error_response("Unexpected Error", str(e))]


async def handle_analyze_prompt(arguments: dict[str, Any]) -> list[types.TextContent]:
    """
    Handle the analyze_prompt tool.

    Analyzes a prompt's complexity without executing it.
    """
    prompt = arguments.get("prompt")

    if not prompt:
        raise ValueError("Prompt is required")

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(
                f"{API_BASE_URL}/analyze",
                json={"prompt": prompt}
            )
            response.raise_for_status()
            data = response.json()

            result = "**Prompt Analysis**\n\n"

            result += f"- Complexity: {data.get('complexity', 'unknown')}\n"
            result += f"- Token Count: {data.get('token_count', 0)}\n"
            result += f"- Recommended Provider: {data.get('recommended_provider', 'unknown')}\n"
            result += f"- Recommended Model: {data.get('recommended_model', 'unknown')}\n"

            keywords = data.get('keywords_found', [])
            if keywords:
                result += f"- Detected Keywords: {', '.join(keywords)}\n"

            # Explain the routing decision
            result += "\n**Routing Logic:**\n"
            complexity = data.get('complexity', 'simple')
            if complexity == 'complex':
                result += "This prompt is classified as COMPLEX because it contains "
                result += "technical keywords or requires sophisticated reasoning. "
                result += "It will be routed to Claude Haiku for better accuracy."
            else:
                result += "This prompt is classified as SIMPLE because it's a "
                result += "straightforward query. It will be routed to Gemini Flash "
                result += "for cost efficiency."

            return [types.TextContent(type="text", text=result)]

    except httpx.ConnectError:
        return [_connection_error_response()]
    except httpx.HTTPError as e:
        return [_error_response("API Error", str(e))]
    except Exception as e:
        logger.exception("Unexpected error in analyze_prompt")
        return [_error_response("Unexpected Error", str(e))]


async def handle_get_cache_analytics(arguments: dict[str, Any]) -> list[types.TextContent]:
    """
    Handle the get_cache_analytics tool.

    Retrieves comprehensive cache analytics with per-provider breakdown.
    """
    days = arguments.get("days", 7)

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(
                f"{API_BASE_URL}/analytics/cache",
                params={"days": days}
            )
            response.raise_for_status()
            data = response.json()

            result = f"**Cache Analytics (Last {days} Days)**\n\n"

            # Summary section
            summary = data.get("summary", {})
            result += "**Summary:**\n"
            result += f"- Total Cache Entries: {summary.get('total_entries', 0):,}\n"
            result += f"- Total Cache Hits: {summary.get('total_hits', 0):,}\n"
            result += f"- Overall Hit Rate: {summary.get('overall_hit_rate', 0):.2f}x\n"
            result += f"- Average Quality: {summary.get('avg_quality', 0):.2f}\n"
            result += f"- Estimated Savings: ${summary.get('estimated_savings_usd', 0):.2f}\n\n"

            # Per-provider breakdown
            by_provider = data.get("by_provider", [])
            if by_provider:
                result += "**By Provider:**\n"
                for p in by_provider:
                    result += f"- {p.get('provider', 'unknown').title()}: "
                    result += f"{p.get('total_entries', 0)} entries, "
                    result += f"{p.get('total_hits', 0)} hits, "
                    result += f"quality {p.get('avg_quality', 0):.2f}, "
                    result += f"hit rate {p.get('hit_rate', 0):.2f}x\n"
                result += "\n"

            # Recommendations
            recommendations = data.get("recommendations", [])
            if recommendations:
                result += "**Recommendations:**\n"
                for rec in recommendations:
                    result += f"- {rec}\n"

            return [types.TextContent(type="text", text=result)]

    except httpx.ConnectError:
        return [_connection_error_response()]
    except httpx.HTTPError as e:
        return [_error_response("API Error", str(e))]
    except Exception as e:
        logger.exception("Unexpected error in get_cache_analytics")
        return [_error_response("Unexpected Error", str(e))]


async def handle_get_optimization_score(arguments: dict[str, Any]) -> list[types.TextContent]:
    """
    Handle the get_optimization_score tool.

    Retrieves the overall optimization score and cost analytics.
    """
    days = arguments.get("days", 7)

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(
                f"{API_BASE_URL}/analytics/costs",
                params={"days": days}
            )
            response.raise_for_status()
            data = response.json()

            # Get the optimization score prominently
            score = data.get("optimization_score", 0)
            score_emoji = "A+" if score >= 90 else "A" if score >= 80 else "B" if score >= 70 else "C" if score >= 60 else "D" if score >= 50 else "F"

            result = f"**Optimization Score: {score}/100 ({score_emoji})**\n\n"

            # Score breakdown
            breakdown = data.get("optimization_breakdown", {})
            result += "**Score Breakdown:**\n"
            result += f"- Cache Efficiency: {breakdown.get('cache_efficiency_points', 0)}/30 points\n"
            result += f"- Cost Reduction: {breakdown.get('cost_reduction_points', 0)}/50 points\n"
            result += f"- Response Quality: {breakdown.get('quality_points', 0)}/20 points\n\n"

            # Cost summary
            summary = data.get("summary", {})
            result += f"**Cost Summary (Last {days} Days):**\n"
            result += f"- Total Cost: ${summary.get('total_cost_usd', 0):.4f}\n"
            result += f"- Total Requests: {summary.get('total_requests', 0):,}\n"
            result += f"- Avg Cost/Request: ${summary.get('avg_cost_per_request', 0):.6f}\n"
            result += f"- Cache Savings: ${summary.get('cache_savings_usd', 0):.2f}\n"
            result += f"- Cost Reduction: {summary.get('effective_cost_reduction_percent', 0):.1f}%\n\n"

            # By provider
            by_provider = data.get("by_provider", [])
            if by_provider:
                result += "**Cost by Provider:**\n"
                for p in by_provider:
                    result += f"- {p.get('provider', 'unknown')}: "
                    result += f"{p.get('request_count', 0)} requests, "
                    result += f"${p.get('total_cost', 0):.4f}\n"
                result += "\n"

            # By complexity
            by_complexity = data.get("by_complexity", [])
            if by_complexity:
                result += "**Cost by Complexity:**\n"
                for c in by_complexity:
                    result += f"- {c.get('complexity', 'unknown')}: "
                    result += f"{c.get('request_count', 0)} requests, "
                    result += f"${c.get('total_cost', 0):.4f}\n"

            return [types.TextContent(type="text", text=result)]

    except httpx.ConnectError:
        return [_connection_error_response()]
    except httpx.HTTPError as e:
        return [_error_response("API Error", str(e))]
    except Exception as e:
        logger.exception("Unexpected error in get_optimization_score")
        return [_error_response("Unexpected Error", str(e))]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _error_response(title: str, message: str) -> types.TextContent:
    """Create a formatted error response."""
    return types.TextContent(
        type="text",
        text=f"**Error: {title}**\n\n{message}"
    )


def _connection_error_response() -> types.TextContent:
    """Create a connection error response with troubleshooting steps."""
    return types.TextContent(
        type="text",
        text=(
            f"**Cannot Connect to Cost Optimizer**\n\n"
            f"Service URL: {API_BASE_URL}\n\n"
            f"**Troubleshooting Steps:**\n"
            f"1. Ensure the FastAPI service is running:\n"
            f"   ```bash\n"
            f"   cd /path/to/ai-cost-optimizer\n"
            f"   python app/main.py\n"
            f"   ```\n"
            f"2. Check if the URL is accessible:\n"
            f"   ```bash\n"
            f"   curl {API_BASE_URL}/health\n"
            f"   ```\n"
            f"3. Verify COST_OPTIMIZER_API_URL environment variable is set correctly."
        )
    )


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="ai-cost-optimizer",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                )
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
