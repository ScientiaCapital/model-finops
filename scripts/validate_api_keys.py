#!/usr/bin/env python3
"""
API Key Validator - Test all configured API keys and show status.

Usage:
    python scripts/validate_api_keys.py
    python scripts/validate_api_keys.py --json  # Output as JSON
    python scripts/validate_api_keys.py --env .env.production  # Custom env file

This script validates API keys by making lightweight test requests
to each provider. It does NOT make billable API calls.
"""

import os
import sys
import json
import asyncio
import argparse
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from enum import Enum

import httpx
from dotenv import load_dotenv


class Status(Enum):
    CONNECTED = "connected"
    INVALID = "invalid"
    NOT_CONFIGURED = "not_configured"
    ERROR = "error"


@dataclass
class ValidationResult:
    name: str
    status: Status
    message: str
    provider: str
    models_available: Optional[int] = None


# Validator configurations for each provider
VALIDATORS = {
    # LLM Providers
    "ANTHROPIC_API_KEY": {
        "provider": "anthropic",
        "url": "https://api.anthropic.com/v1/models",
        "headers": lambda key: {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
        },
        "success_codes": [200],
        "models_key": "data",
    },
    "GOOGLE_API_KEY": {
        "provider": "google",
        "url_template": "https://generativelanguage.googleapis.com/v1beta/models?key={key}",
        "success_codes": [200],
        "models_key": "models",
    },
    "OPENROUTER_API_KEY": {
        "provider": "openrouter",
        "url": "https://openrouter.ai/api/v1/models",
        "headers": lambda key: {"Authorization": f"Bearer {key}"},
        "success_codes": [200],
        "models_key": "data",
    },
    "GROQ_API_KEY": {
        "provider": "groq",
        "url": "https://api.groq.com/openai/v1/models",
        "headers": lambda key: {"Authorization": f"Bearer {key}"},
        "success_codes": [200],
        "models_key": "data",
    },
    "CEREBRAS_API_KEY": {
        "provider": "cerebras",
        "url": "https://api.cerebras.ai/v1/models",
        "headers": lambda key: {"Authorization": f"Bearer {key}"},
        "success_codes": [200],
        "models_key": "data",
    },
    "TOGETHER_API_KEY": {
        "provider": "together",
        "url": "https://api.together.xyz/v1/models",
        "headers": lambda key: {"Authorization": f"Bearer {key}"},
        "success_codes": [200],
        "models_key": None,  # Returns list directly
    },
    "HUGGINGFACE_API_KEY": {
        "provider": "huggingface",
        "url": "https://huggingface.co/api/whoami-v2",
        "headers": lambda key: {"Authorization": f"Bearer {key}"},
        "success_codes": [200],
        "models_key": None,
    },
    # Voice AI - TTS
    "CARTESIA_API_KEY": {
        "provider": "cartesia",
        "url": "https://api.cartesia.ai/voices",
        "headers": lambda key: {
            "X-API-Key": key,
            "Cartesia-Version": "2024-06-10",
        },
        "success_codes": [200],
        "models_key": None,
    },
    "ELEVENLABS_API_KEY": {
        "provider": "elevenlabs",
        "url": "https://api.elevenlabs.io/v1/voices",
        "headers": lambda key: {"xi-api-key": key},
        "success_codes": [200],
        "models_key": "voices",
    },
    # Voice AI - STT
    "DEEPGRAM_API_KEY": {
        "provider": "deepgram",
        "url": "https://api.deepgram.com/v1/projects",
        "headers": lambda key: {"Authorization": f"Token {key}"},
        "success_codes": [200],
        "models_key": "projects",
    },
    "ASSEMBLYAI_API_KEY": {
        "provider": "assemblyai",
        "url": "https://api.assemblyai.com/v2/transcript",
        "headers": lambda key: {"authorization": key},
        "method": "GET",
        "success_codes": [200],
        "models_key": "transcripts",
    },
    # Infrastructure
    "SUPABASE_URL": {
        "provider": "supabase",
        "url_from_env": "SUPABASE_URL",
        "url_suffix": "/rest/v1/",
        "headers_from_env": {
            "apikey": "SUPABASE_ANON_KEY",
            "Authorization": "Bearer {SUPABASE_ANON_KEY}",
        },
        "success_codes": [200],
        "models_key": None,
    },
    "RAILWAY_API_TOKEN": {
        "provider": "railway",
        "url": "https://backboard.railway.app/graphql/v2",
        "headers": lambda key: {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        "method": "POST",
        "body": '{"query": "{ me { id } }"}',
        "success_codes": [200],
        "models_key": None,
    },
    "RUNPOD_API_KEY": {
        "provider": "runpod",
        "url": "https://api.runpod.io/v2/user/current",
        "headers": lambda key: {"Authorization": f"Bearer {key}"},
        "success_codes": [200],
        "models_key": None,
    },
    # AI Media
    "RUNWAY_API_KEY": {
        "provider": "runway",
        "url": "https://api.runwayml.com/v1/organizations",
        "headers": lambda key: {"Authorization": f"Bearer {key}"},
        "success_codes": [200],
        "models_key": None,
    },
    # Observability
    "LANGCHAIN_API_KEY": {
        "provider": "langsmith",
        "url": "https://api.smith.langchain.com/api/v1/info",
        "headers": lambda key: {"x-api-key": key},
        "success_codes": [200],
        "models_key": None,
    },
    # Billing
    "STRIPE_SECRET_KEY": {
        "provider": "stripe",
        "url": "https://api.stripe.com/v1/balance",
        "headers": lambda key: {"Authorization": f"Bearer {key}"},
        "success_codes": [200],
        "models_key": None,
    },
}


async def validate_key(
    client: httpx.AsyncClient,
    env_name: str,
    config: dict,
) -> ValidationResult:
    """Validate a single API key."""
    key = os.getenv(env_name)
    provider = config["provider"]

    if not key:
        return ValidationResult(
            name=env_name,
            status=Status.NOT_CONFIGURED,
            message="Not configured",
            provider=provider,
        )

    # Special handling for Supabase (needs multiple env vars)
    if env_name == "SUPABASE_URL":
        anon_key = os.getenv("SUPABASE_ANON_KEY")
        if not anon_key:
            return ValidationResult(
                name=env_name,
                status=Status.NOT_CONFIGURED,
                message="SUPABASE_ANON_KEY not set",
                provider=provider,
            )
        url = key.rstrip("/") + "/rest/v1/"
        headers = {
            "apikey": anon_key,
            "Authorization": f"Bearer {anon_key}",
        }
    else:
        # Build URL
        if "url_template" in config:
            url = config["url_template"].format(key=key)
            headers = {}
        else:
            url = config["url"]
            headers = config.get("headers", lambda k: {})(key)

    try:
        method = config.get("method", "GET")
        body = config.get("body")
        if method == "GET":
            response = await client.get(url, headers=headers, timeout=10.0)
        else:
            response = await client.post(url, headers=headers, content=body, timeout=10.0)

        if response.status_code in config["success_codes"]:
            # Count models if available
            models_count = None
            if config.get("models_key"):
                try:
                    data = response.json()
                    models_data = data.get(config["models_key"], [])
                    if isinstance(models_data, list):
                        models_count = len(models_data)
                except Exception:
                    pass

            return ValidationResult(
                name=env_name,
                status=Status.CONNECTED,
                message="Connected",
                provider=provider,
                models_available=models_count,
            )
        elif response.status_code == 401:
            return ValidationResult(
                name=env_name,
                status=Status.INVALID,
                message="Invalid API key",
                provider=provider,
            )
        elif response.status_code == 403:
            return ValidationResult(
                name=env_name,
                status=Status.INVALID,
                message="Access denied (check permissions)",
                provider=provider,
            )
        else:
            return ValidationResult(
                name=env_name,
                status=Status.ERROR,
                message=f"HTTP {response.status_code}",
                provider=provider,
            )
    except httpx.TimeoutException:
        return ValidationResult(
            name=env_name,
            status=Status.ERROR,
            message="Timeout (service may be down)",
            provider=provider,
        )
    except httpx.ConnectError:
        return ValidationResult(
            name=env_name,
            status=Status.ERROR,
            message="Connection failed",
            provider=provider,
        )
    except Exception as e:
        return ValidationResult(
            name=env_name,
            status=Status.ERROR,
            message=str(e)[:50],
            provider=provider,
        )


async def validate_all_keys() -> list[ValidationResult]:
    """Validate all configured API keys."""
    async with httpx.AsyncClient() as client:
        tasks = [
            validate_key(client, name, config)
            for name, config in VALIDATORS.items()
        ]
        return await asyncio.gather(*tasks)


def print_table(results: list[ValidationResult]) -> None:
    """Print results as a formatted table."""
    # ANSI colors
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

    # Status symbols and colors
    status_display = {
        Status.CONNECTED: (f"{GREEN}✅{RESET}", "Connected"),
        Status.INVALID: (f"{RED}❌{RESET}", "Invalid"),
        Status.NOT_CONFIGURED: (f"{YELLOW}⚠️ {RESET}", "Not configured"),
        Status.ERROR: (f"{RED}⚠️ {RESET}", "Error"),
    }

    # Calculate column widths
    max_name = max(len(r.name) for r in results)
    max_msg = max(len(r.message) for r in results)

    # Print header
    width = max_name + max_msg + 30
    print()
    print(f"╭{'─' * width}╮")
    print(f"│{BOLD}{'AI Stack Optimizer - API Key Validator':^{width}}{RESET}│")
    print(f"├{'─' * width}┤")

    # Group by category
    categories = {
        "LLM Providers": ["anthropic", "google", "openrouter", "groq", "cerebras", "together"],
        "Voice AI (TTS)": ["cartesia", "elevenlabs"],
        "Voice AI (STT)": ["deepgram", "assemblyai"],
        "Infrastructure": ["supabase", "vercel"],
        "Observability": ["langsmith"],
        "Billing": ["stripe"],
    }

    for category, providers in categories.items():
        category_results = [r for r in results if r.provider in providers]
        if not category_results:
            continue

        print(f"│ {BOLD}{category}{RESET}{' ' * (width - len(category) - 2)}│")

        for r in category_results:
            symbol, _ = status_display[r.status]
            models_str = f" ({r.models_available} models)" if r.models_available else ""
            line = f"  {r.name:<{max_name}}  {symbol} {r.message}{models_str}"
            padding = width - len(line) + len(symbol) - 2  # Account for ANSI codes
            print(f"│{line}{' ' * padding}│")

        print(f"│{' ' * width}│")

    # Summary
    connected = sum(1 for r in results if r.status == Status.CONNECTED)
    total = len(results)

    print(f"├{'─' * width}┤")
    summary = f"Total: {connected}/{total} configured"
    print(f"│{summary:^{width}}│")
    print(f"╰{'─' * width}╯")
    print()


def print_json(results: list[ValidationResult]) -> None:
    """Print results as JSON."""
    output = {
        "results": [
            {
                "name": r.name,
                "status": r.status.value,
                "message": r.message,
                "provider": r.provider,
                "models_available": r.models_available,
            }
            for r in results
        ],
        "summary": {
            "connected": sum(1 for r in results if r.status == Status.CONNECTED),
            "invalid": sum(1 for r in results if r.status == Status.INVALID),
            "not_configured": sum(1 for r in results if r.status == Status.NOT_CONFIGURED),
            "errors": sum(1 for r in results if r.status == Status.ERROR),
            "total": len(results),
        }
    }
    print(json.dumps(output, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Validate AI Stack Optimizer API keys")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--env", default=".env", help="Path to .env file")
    args = parser.parse_args()

    # Load environment
    env_path = Path(args.env)
    if env_path.exists():
        load_dotenv(env_path)
    else:
        # Try from project root
        project_root = Path(__file__).parent.parent
        load_dotenv(project_root / ".env")

    # Run validation
    results = asyncio.run(validate_all_keys())

    # Output
    if args.json:
        print_json(results)
    else:
        print_table(results)

    # Exit code: 0 if all configured keys are valid, 1 otherwise
    invalid_count = sum(1 for r in results if r.status == Status.INVALID)
    sys.exit(1 if invalid_count > 0 else 0)


if __name__ == "__main__":
    main()
