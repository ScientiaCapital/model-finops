"""
Provider Status Router - Check API key connectivity and provider status.

Endpoints:
- GET /api/status/providers - Get status of all providers
- GET /api/status/providers/{provider} - Get status of specific provider
- POST /api/status/validate - Validate a specific API key
- GET /api/status/setup-links - Get setup links for all providers
"""

import os
import asyncio
import logging
from typing import Optional
from enum import Enum

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/status", tags=["status"])


class ProviderStatus(str, Enum):
    CONNECTED = "connected"
    INVALID = "invalid"
    NOT_CONFIGURED = "not_configured"
    ERROR = "error"


class ProviderInfo(BaseModel):
    """Information about a provider's status."""
    name: str
    display_name: str
    status: ProviderStatus
    message: str
    category: str
    setup_url: str
    models_available: Optional[int] = None
    env_vars: list[str]


class ProvidersStatusResponse(BaseModel):
    """Response for all providers status."""
    providers: list[ProviderInfo]
    summary: dict
    setup_progress: float = Field(description="Percentage of providers configured (0-100)")


class ValidateKeyRequest(BaseModel):
    """Request to validate a specific API key."""
    provider: str
    api_key: str


class ValidateKeyResponse(BaseModel):
    """Response from key validation."""
    valid: bool
    message: str
    models_available: Optional[int] = None


class SetupLink(BaseModel):
    """Setup link for a provider."""
    provider: str
    display_name: str
    category: str
    setup_url: str
    env_vars: list[str]
    instructions: str


# Provider configuration
PROVIDER_CONFIG = {
    # LLM Providers
    "anthropic": {
        "display_name": "Anthropic Claude",
        "category": "LLM Providers",
        "setup_url": "https://console.anthropic.com/settings/keys",
        "env_vars": ["ANTHROPIC_API_KEY"],
        "instructions": "Click 'Create Key' → Copy the key",
        "validator": {
            "url": "https://api.anthropic.com/v1/models",
            "headers": lambda key: {"x-api-key": key, "anthropic-version": "2023-06-01"},
            "models_key": "data",
        }
    },
    "google": {
        "display_name": "Google AI / Gemini",
        "category": "LLM Providers",
        "setup_url": "https://aistudio.google.com/app/apikey",
        "env_vars": ["GOOGLE_API_KEY"],
        "instructions": "Click 'Create API Key' button",
        "validator": {
            "url_template": "https://generativelanguage.googleapis.com/v1beta/models?key={key}",
            "models_key": "models",
        }
    },
    "openrouter": {
        "display_name": "OpenRouter",
        "category": "LLM Providers",
        "setup_url": "https://openrouter.ai/keys",
        "env_vars": ["OPENROUTER_API_KEY"],
        "instructions": "Create new key on Keys page",
        "validator": {
            "url": "https://openrouter.ai/api/v1/models",
            "headers": lambda key: {"Authorization": f"Bearer {key}"},
            "models_key": "data",
        }
    },
    "groq": {
        "display_name": "Groq",
        "category": "LLM Providers",
        "setup_url": "https://console.groq.com/keys",
        "env_vars": ["GROQ_API_KEY"],
        "instructions": "Create API Key in console",
        "validator": {
            "url": "https://api.groq.com/openai/v1/models",
            "headers": lambda key: {"Authorization": f"Bearer {key}"},
            "models_key": "data",
        }
    },
    "cerebras": {
        "display_name": "Cerebras",
        "category": "LLM Providers",
        "setup_url": "https://cloud.cerebras.ai/platform",
        "env_vars": ["CEREBRAS_API_KEY"],
        "instructions": "Platform → API section",
        "validator": {
            "url": "https://api.cerebras.ai/v1/models",
            "headers": lambda key: {"Authorization": f"Bearer {key}"},
            "models_key": "data",
        }
    },
    "together": {
        "display_name": "Together AI",
        "category": "LLM Providers",
        "setup_url": "https://api.together.xyz/settings/api-keys",
        "env_vars": ["TOGETHER_API_KEY"],
        "instructions": "Settings → API Keys",
        "validator": {
            "url": "https://api.together.xyz/v1/models",
            "headers": lambda key: {"Authorization": f"Bearer {key}"},
        }
    },
    "huggingface": {
        "display_name": "Hugging Face",
        "category": "LLM Providers",
        "setup_url": "https://huggingface.co/settings/tokens",
        "env_vars": ["HUGGINGFACE_API_KEY"],
        "instructions": "Settings → Access Tokens → New token",
        "validator": {
            "url": "https://huggingface.co/api/whoami-v2",
            "headers": lambda key: {"Authorization": f"Bearer {key}"},
        }
    },
    # Voice AI - TTS
    "cartesia": {
        "display_name": "Cartesia",
        "category": "Voice AI (TTS)",
        "setup_url": "https://play.cartesia.ai/console",
        "env_vars": ["CARTESIA_API_KEY"],
        "instructions": "Console → API section",
        "validator": {
            "url": "https://api.cartesia.ai/voices",
            "headers": lambda key: {"X-API-Key": key, "Cartesia-Version": "2024-06-10"},
        }
    },
    "elevenlabs": {
        "display_name": "ElevenLabs",
        "category": "Voice AI (TTS)",
        "setup_url": "https://elevenlabs.io/app/settings/api-keys",
        "env_vars": ["ELEVENLABS_API_KEY"],
        "instructions": "Profile → API Keys",
        "validator": {
            "url": "https://api.elevenlabs.io/v1/voices",
            "headers": lambda key: {"xi-api-key": key},
            "models_key": "voices",
        }
    },
    # Voice AI - STT
    "deepgram": {
        "display_name": "Deepgram",
        "category": "Voice AI (STT)",
        "setup_url": "https://console.deepgram.com",
        "env_vars": ["DEEPGRAM_API_KEY"],
        "instructions": "Project → Keys",
        "validator": {
            "url": "https://api.deepgram.com/v1/projects",
            "headers": lambda key: {"Authorization": f"Token {key}"},
            "models_key": "projects",
        }
    },
    "assemblyai": {
        "display_name": "AssemblyAI",
        "category": "Voice AI (STT)",
        "setup_url": "https://www.assemblyai.com/app/account",
        "env_vars": ["ASSEMBLYAI_API_KEY"],
        "instructions": "Account page → API Key",
        "validator": {
            "url": "https://api.assemblyai.com/v2/transcript",
            "headers": lambda key: {"authorization": key},
            "models_key": "transcripts",
        }
    },
    # Infrastructure
    "supabase": {
        "display_name": "Supabase",
        "category": "Infrastructure",
        "setup_url": "https://supabase.com/dashboard/project/_/settings/api",
        "env_vars": ["SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_KEY", "SUPABASE_JWT_SECRET"],
        "instructions": "Project → Settings → API",
        "validator": None,  # Special handling
    },
    "vercel": {
        "display_name": "Vercel",
        "category": "Infrastructure",
        "setup_url": "https://vercel.com/account/tokens",
        "env_vars": ["VERCEL_TOKEN", "VERCEL_ORG_ID", "VERCEL_PROJECT_ID"],
        "instructions": "Account → Tokens",
        "validator": None,  # Special handling
    },
    "railway": {
        "display_name": "Railway",
        "category": "Infrastructure",
        "setup_url": "https://railway.app/account/tokens",
        "env_vars": ["RAILWAY_API_TOKEN"],
        "instructions": "Account → Tokens",
        "validator": None,  # GraphQL API, special handling needed
    },
    "runpod": {
        "display_name": "RunPod",
        "category": "Infrastructure",
        "setup_url": "https://www.runpod.io/console/user/settings",
        "env_vars": ["RUNPOD_API_KEY"],
        "instructions": "Settings → API Keys",
        "validator": {
            "url": "https://api.runpod.io/v2/user/current",
            "headers": lambda key: {"Authorization": f"Bearer {key}"},
        }
    },
    # AI Media
    "runway": {
        "display_name": "Runway",
        "category": "AI Media",
        "setup_url": "https://app.runwayml.com/account/api-keys",
        "env_vars": ["RUNWAY_API_KEY"],
        "instructions": "Account → API Keys",
        "validator": {
            "url": "https://api.runwayml.com/v1/organizations",
            "headers": lambda key: {"Authorization": f"Bearer {key}"},
        }
    },
    # Observability
    "langsmith": {
        "display_name": "LangSmith",
        "category": "Observability",
        "setup_url": "https://smith.langchain.com/settings",
        "env_vars": ["LANGCHAIN_API_KEY"],
        "instructions": "Settings → API Keys",
        "validator": {
            "url": "https://api.smith.langchain.com/api/v1/info",
            "headers": lambda key: {"x-api-key": key},
        }
    },
    # Billing
    "stripe": {
        "display_name": "Stripe",
        "category": "Billing",
        "setup_url": "https://dashboard.stripe.com/apikeys",
        "env_vars": ["STRIPE_SECRET_KEY", "STRIPE_PUBLISHABLE_KEY", "STRIPE_WEBHOOK_SECRET"],
        "instructions": "Developers → API keys",
        "validator": {
            "url": "https://api.stripe.com/v1/balance",
            "headers": lambda key: {"Authorization": f"Bearer {key}"},
        }
    },
}


async def validate_provider(
    client: httpx.AsyncClient,
    provider: str,
    api_key: Optional[str] = None,
) -> tuple[ProviderStatus, str, Optional[int]]:
    """Validate a single provider's API key."""
    config = PROVIDER_CONFIG.get(provider)
    if not config:
        return ProviderStatus.ERROR, "Unknown provider", None

    # Get the key from env if not provided
    if api_key is None:
        env_var = config["env_vars"][0]
        api_key = os.getenv(env_var)

    if not api_key:
        return ProviderStatus.NOT_CONFIGURED, "Not configured", None

    validator = config.get("validator")
    if not validator:
        # For providers without validators, just check env var exists
        return ProviderStatus.CONNECTED, "Configured", None

    try:
        # Build URL
        if "url_template" in validator:
            url = validator["url_template"].format(key=api_key)
            headers = {}
        else:
            url = validator["url"]
            headers_fn = validator.get("headers", lambda k: {})
            headers = headers_fn(api_key)

        response = await client.get(url, headers=headers, timeout=10.0)

        if response.status_code == 200:
            models_count = None
            if validator.get("models_key"):
                try:
                    data = response.json()
                    models_data = data.get(validator["models_key"], [])
                    if isinstance(models_data, list):
                        models_count = len(models_data)
                except Exception:
                    pass
            return ProviderStatus.CONNECTED, "Connected", models_count
        elif response.status_code == 401:
            return ProviderStatus.INVALID, "Invalid API key", None
        elif response.status_code == 403:
            return ProviderStatus.INVALID, "Access denied", None
        else:
            return ProviderStatus.ERROR, f"HTTP {response.status_code}", None

    except httpx.TimeoutException:
        return ProviderStatus.ERROR, "Timeout", None
    except Exception as e:
        logger.warning(f"Error validating {provider}: {e}")
        return ProviderStatus.ERROR, str(e)[:50], None


@router.get("/providers", response_model=ProvidersStatusResponse)
async def get_providers_status(request: Request):
    """
    Get status of all configured providers.

    Returns connection status, setup URLs, and progress percentage.
    """
    async with httpx.AsyncClient() as client:
        providers = []

        for name, config in PROVIDER_CONFIG.items():
            status, message, models = await validate_provider(client, name)

            providers.append(ProviderInfo(
                name=name,
                display_name=config["display_name"],
                status=status,
                message=message,
                category=config["category"],
                setup_url=config["setup_url"],
                models_available=models,
                env_vars=config["env_vars"],
            ))

    # Calculate summary
    connected = sum(1 for p in providers if p.status == ProviderStatus.CONNECTED)
    configured = sum(1 for p in providers if p.status != ProviderStatus.NOT_CONFIGURED)
    total = len(providers)

    return ProvidersStatusResponse(
        providers=providers,
        summary={
            "connected": connected,
            "configured": configured,
            "not_configured": total - configured,
            "total": total,
        },
        setup_progress=round((configured / total) * 100, 1) if total > 0 else 0,
    )


@router.get("/providers/{provider}", response_model=ProviderInfo)
async def get_provider_status(provider: str, request: Request):
    """Get status of a specific provider."""
    if provider not in PROVIDER_CONFIG:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider}")

    config = PROVIDER_CONFIG[provider]

    async with httpx.AsyncClient() as client:
        status, message, models = await validate_provider(client, provider)

    return ProviderInfo(
        name=provider,
        display_name=config["display_name"],
        status=status,
        message=message,
        category=config["category"],
        setup_url=config["setup_url"],
        models_available=models,
        env_vars=config["env_vars"],
    )


@router.post("/validate", response_model=ValidateKeyResponse)
async def validate_api_key(body: ValidateKeyRequest, request: Request):
    """
    Validate a specific API key before saving.

    Use this endpoint to test a key before adding it to your config.
    """
    if body.provider not in PROVIDER_CONFIG:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {body.provider}")

    async with httpx.AsyncClient() as client:
        status, message, models = await validate_provider(
            client, body.provider, api_key=body.api_key
        )

    return ValidateKeyResponse(
        valid=status == ProviderStatus.CONNECTED,
        message=message,
        models_available=models,
    )


@router.get("/setup-links", response_model=list[SetupLink])
async def get_setup_links(request: Request, category: Optional[str] = None):
    """
    Get setup links for all providers.

    Optionally filter by category (e.g., "LLM Providers", "Voice AI (TTS)").
    """
    links = []

    for name, config in PROVIDER_CONFIG.items():
        if category and config["category"] != category:
            continue

        links.append(SetupLink(
            provider=name,
            display_name=config["display_name"],
            category=config["category"],
            setup_url=config["setup_url"],
            env_vars=config["env_vars"],
            instructions=config["instructions"],
        ))

    return links


@router.get("/categories")
async def get_categories(request: Request):
    """Get list of provider categories."""
    categories = set()
    for config in PROVIDER_CONFIG.values():
        categories.add(config["category"])

    return {
        "categories": sorted(list(categories)),
        "providers_by_category": {
            cat: [name for name, cfg in PROVIDER_CONFIG.items() if cfg["category"] == cat]
            for cat in sorted(categories)
        }
    }
