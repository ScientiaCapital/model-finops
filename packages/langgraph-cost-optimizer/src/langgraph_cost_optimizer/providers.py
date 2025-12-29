"""
Provider pricing registry for LLM and service cost calculation.

Prices as of December 2025:
- LLM: per 1M tokens (input/output)
- Audio TTS: per 1M characters
- Audio STT: per minute or per second
- Infrastructure: per unit (varies by service)
"""

from dataclasses import dataclass
from typing import Optional, Union
from enum import Enum


class PricingUnit(Enum):
    """Units for pricing calculation."""
    TOKENS_1M = "tokens_1m"           # Per 1M tokens (LLMs)
    CHARACTERS_1M = "characters_1m"    # Per 1M characters (TTS)
    MINUTES = "minutes"                # Per minute (STT, compute)
    SECONDS = "seconds"                # Per second (real-time)
    REQUESTS = "requests"              # Per request/invocation
    GB_HOURS = "gb_hours"              # Per GB-hour (storage/compute)
    INVOCATIONS = "invocations"        # Per function invocation


@dataclass(frozen=True)
class ModelPricing:
    """Pricing information for a model (token-based)."""
    input_price: float  # $ per 1M input tokens
    output_price: float  # $ per 1M output tokens
    context_window: int = 128_000  # Default context size
    provider: str = "unknown"


@dataclass(frozen=True)
class ServicePricing:
    """Pricing information for non-token services (audio, infra)."""
    price: float  # $ per unit
    unit: PricingUnit
    provider: str
    tier: str = "default"  # Plan tier (free, pro, enterprise)
    notes: str = ""  # Additional pricing notes


# Comprehensive pricing registry
PROVIDER_PRICING: dict[str, ModelPricing] = {
    # ==========================================================================
    # Anthropic Claude Models (Direct API)
    # ==========================================================================

    # Claude 4.5 Family
    "claude-opus-4-5-20251101": ModelPricing(15.00, 75.00, 200_000, "anthropic"),
    "claude-opus-4-5": ModelPricing(15.00, 75.00, 200_000, "anthropic"),
    "claude-sonnet-4-5-20250929": ModelPricing(3.00, 15.00, 200_000, "anthropic"),
    "claude-sonnet-4-5": ModelPricing(3.00, 15.00, 200_000, "anthropic"),
    "claude-haiku-4-5-20251001": ModelPricing(1.00, 5.00, 200_000, "anthropic"),
    "claude-haiku-4-5": ModelPricing(1.00, 5.00, 200_000, "anthropic"),

    # Claude 4 Family
    "claude-opus-4-20250514": ModelPricing(15.00, 75.00, 200_000, "anthropic"),
    "claude-opus-4": ModelPricing(15.00, 75.00, 200_000, "anthropic"),
    "claude-sonnet-4-20250514": ModelPricing(3.00, 15.00, 200_000, "anthropic"),
    "claude-sonnet-4": ModelPricing(3.00, 15.00, 200_000, "anthropic"),

    # Claude 3.5 Family (legacy)
    "claude-3-5-sonnet-20241022": ModelPricing(3.00, 15.00, 200_000, "anthropic"),
    "claude-3-5-haiku-20241022": ModelPricing(1.00, 5.00, 200_000, "anthropic"),

    # Claude 3 Family (legacy)
    "claude-3-opus-20240229": ModelPricing(15.00, 75.00, 200_000, "anthropic"),
    "claude-3-sonnet-20240229": ModelPricing(3.00, 15.00, 200_000, "anthropic"),
    "claude-3-haiku-20240307": ModelPricing(0.25, 1.25, 200_000, "anthropic"),

    # ==========================================================================
    # OpenRouter Models
    # ==========================================================================

    # Anthropic via OpenRouter
    "anthropic/claude-opus-4.5": ModelPricing(15.00, 75.00, 200_000, "openrouter"),
    "anthropic/claude-sonnet-4.5": ModelPricing(3.00, 15.00, 200_000, "openrouter"),
    "anthropic/claude-haiku-4.5": ModelPricing(1.00, 5.00, 200_000, "openrouter"),
    "anthropic/claude-3-haiku": ModelPricing(0.25, 1.25, 200_000, "openrouter"),
    "anthropic/claude-3.5-sonnet": ModelPricing(3.00, 15.00, 200_000, "openrouter"),

    # DeepSeek (Chinese - Cost Effective)
    "deepseek/deepseek-chat": ModelPricing(0.30, 1.20, 164_000, "openrouter"),
    "deepseek/deepseek-v3.1-terminus": ModelPricing(0.20, 0.80, 131_000, "openrouter"),
    "deepseek/deepseek-v3.2": ModelPricing(0.27, 0.40, 131_000, "openrouter"),
    "deepseek/deepseek-r1": ModelPricing(0.55, 2.19, 64_000, "openrouter"),
    "deepseek/deepseek-coder": ModelPricing(0.14, 0.28, 128_000, "openrouter"),

    # Qwen (Chinese - Cost Effective)
    "qwen/qwen-2.5-72b-instruct": ModelPricing(0.35, 0.40, 128_000, "openrouter"),
    "qwen/qwen-max": ModelPricing(1.60, 6.40, 32_000, "openrouter"),
    "qwen/qwen-plus": ModelPricing(0.40, 1.20, 131_000, "openrouter"),
    "qwen/qwen-2.5-coder-7b-instruct": ModelPricing(0.03, 0.09, 33_000, "openrouter"),
    "qwen/qwen-2.5-coder-32b-instruct": ModelPricing(0.07, 0.16, 131_000, "openrouter"),

    # Baidu ERNIE (Chinese)
    "baidu/ernie-4.5-300b-a47b": ModelPricing(0.22, 0.88, 131_000, "openrouter"),

    # Meta Llama via OpenRouter
    "meta-llama/llama-3.1-8b-instruct:free": ModelPricing(0.0, 0.0, 128_000, "openrouter"),
    "meta-llama/llama-3.1-70b-instruct": ModelPricing(0.52, 0.75, 128_000, "openrouter"),
    "meta-llama/llama-3.1-405b-instruct": ModelPricing(2.70, 2.70, 128_000, "openrouter"),
    "meta-llama/llama-3.3-70b-instruct": ModelPricing(0.30, 0.30, 128_000, "openrouter"),

    # Google via OpenRouter
    "google/gemini-flash-1.5": ModelPricing(0.075, 0.30, 1_000_000, "openrouter"),
    "google/gemini-pro-1.5": ModelPricing(1.25, 5.00, 2_000_000, "openrouter"),

    # OpenAI via OpenRouter
    "openai/gpt-4o": ModelPricing(2.50, 10.00, 128_000, "openrouter"),
    "openai/gpt-4o-mini": ModelPricing(0.15, 0.60, 128_000, "openrouter"),
    "openai/gpt-3.5-turbo": ModelPricing(0.50, 1.50, 16_000, "openrouter"),

    # ==========================================================================
    # Google Gemini (Direct API)
    # ==========================================================================
    "gemini-1.5-flash": ModelPricing(0.075, 0.30, 1_000_000, "google"),
    "gemini-1.5-pro": ModelPricing(1.25, 5.00, 2_000_000, "google"),
    "gemini-2.0-flash-exp": ModelPricing(0.0, 0.0, 1_000_000, "google"),  # Free preview

    # ==========================================================================
    # Groq (Ultra-fast LPU)
    # ==========================================================================
    "llama-3.3-70b-versatile": ModelPricing(0.59, 0.79, 128_000, "groq"),
    "llama-3.1-8b-instant": ModelPricing(0.05, 0.08, 128_000, "groq"),
    "llama-3.2-90b-vision-preview": ModelPricing(0.90, 0.90, 128_000, "groq"),
    "mixtral-8x7b-32768": ModelPricing(0.24, 0.24, 32_000, "groq"),
    "gemma2-9b-it": ModelPricing(0.20, 0.20, 8_000, "groq"),

    # ==========================================================================
    # Cerebras (Ultra-fast Wafer-Scale)
    # ==========================================================================
    "llama3.1-8b": ModelPricing(0.10, 0.10, 128_000, "cerebras"),
    "llama3.1-70b": ModelPricing(0.60, 0.60, 128_000, "cerebras"),

    # ==========================================================================
    # Together AI (Fine-tuned models)
    # ==========================================================================
    "meta-llama/Llama-3.2-3B-Instruct-Turbo": ModelPricing(0.06, 0.06, 131_000, "together"),
    "meta-llama/Llama-3.2-11B-Vision-Instruct-Turbo": ModelPricing(0.18, 0.18, 131_000, "together"),
    "meta-llama/Llama-3.2-90B-Vision-Instruct-Turbo": ModelPricing(0.88, 0.88, 131_000, "together"),
    "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo": ModelPricing(0.18, 0.18, 131_000, "together"),
    "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo": ModelPricing(0.88, 0.88, 131_000, "together"),
    "meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo": ModelPricing(3.50, 3.50, 131_000, "together"),
    "mistralai/Mixtral-8x7B-Instruct-v0.1": ModelPricing(0.60, 0.60, 32_000, "together"),
    "mistralai/Mistral-7B-Instruct-v0.3": ModelPricing(0.20, 0.20, 32_000, "together"),

    # ==========================================================================
    # Voyage AI (Embeddings)
    # ==========================================================================
    "voyage-3": ModelPricing(0.06, 0.0, 32_000, "voyage"),
    "voyage-3-lite": ModelPricing(0.02, 0.0, 32_000, "voyage"),
    "voyage-code-3": ModelPricing(0.18, 0.0, 32_000, "voyage"),
}


# =============================================================================
# SERVICE PRICING (Non-token based: Audio, Infrastructure, Observability)
# =============================================================================

SERVICE_PRICING: dict[str, ServicePricing] = {
    # ==========================================================================
    # Cartesia (Voice AI - TTS)
    # https://cartesia.ai/pricing
    # ==========================================================================
    "cartesia/sonic-english": ServicePricing(
        price=0.042, unit=PricingUnit.SECONDS, provider="cartesia",
        notes="Real-time voice, ~150 chars/sec"
    ),
    "cartesia/sonic-multilingual": ServicePricing(
        price=0.06, unit=PricingUnit.SECONDS, provider="cartesia",
        notes="29 languages supported"
    ),
    "cartesia/voice-clone": ServicePricing(
        price=5.00, unit=PricingUnit.REQUESTS, provider="cartesia",
        notes="Per voice clone creation"
    ),

    # ==========================================================================
    # ElevenLabs (Voice AI - TTS)
    # https://elevenlabs.io/pricing
    # ==========================================================================
    "elevenlabs/multilingual-v2": ServicePricing(
        price=0.30, unit=PricingUnit.CHARACTERS_1M, provider="elevenlabs",
        tier="creator", notes="$0.30/1K chars = $300/1M"
    ),
    "elevenlabs/turbo-v2": ServicePricing(
        price=0.18, unit=PricingUnit.CHARACTERS_1M, provider="elevenlabs",
        tier="creator", notes="Faster, English-focused"
    ),
    "elevenlabs/voice-clone-instant": ServicePricing(
        price=0.0, unit=PricingUnit.REQUESTS, provider="elevenlabs",
        tier="creator", notes="Included in subscription"
    ),

    # ==========================================================================
    # Deepgram (Speech-to-Text)
    # https://deepgram.com/pricing
    # ==========================================================================
    "deepgram/nova-2": ServicePricing(
        price=0.0043, unit=PricingUnit.MINUTES, provider="deepgram",
        notes="Best accuracy, $0.0043/min = $0.26/hour"
    ),
    "deepgram/nova-2-meeting": ServicePricing(
        price=0.0048, unit=PricingUnit.MINUTES, provider="deepgram",
        notes="Optimized for meetings"
    ),
    "deepgram/whisper-large": ServicePricing(
        price=0.0048, unit=PricingUnit.MINUTES, provider="deepgram",
        notes="OpenAI Whisper via Deepgram"
    ),
    "deepgram/nova-2-streaming": ServicePricing(
        price=0.0059, unit=PricingUnit.MINUTES, provider="deepgram",
        notes="Real-time streaming"
    ),

    # ==========================================================================
    # AssemblyAI (Speech-to-Text)
    # https://www.assemblyai.com/pricing
    # ==========================================================================
    "assemblyai/best": ServicePricing(
        price=0.00017, unit=PricingUnit.SECONDS, provider="assemblyai",
        notes="$0.00017/sec = $0.37/hour"
    ),
    "assemblyai/nano": ServicePricing(
        price=0.00008, unit=PricingUnit.SECONDS, provider="assemblyai",
        notes="Faster, lower accuracy"
    ),
    "assemblyai/streaming": ServicePricing(
        price=0.00025, unit=PricingUnit.SECONDS, provider="assemblyai",
        notes="Real-time streaming"
    ),

    # ==========================================================================
    # LangSmith (Observability)
    # https://www.langchain.com/langsmith
    # ==========================================================================
    "langsmith/traces": ServicePricing(
        price=0.0, unit=PricingUnit.REQUESTS, provider="langsmith",
        tier="free", notes="5K traces/month free, $39/mo for 50K"
    ),
    "langsmith/traces-pro": ServicePricing(
        price=0.00078, unit=PricingUnit.REQUESTS, provider="langsmith",
        tier="pro", notes="$39/50K traces = ~$0.00078/trace"
    ),

    # ==========================================================================
    # Supabase (Backend Infrastructure)
    # https://supabase.com/pricing
    # ==========================================================================
    "supabase/database-compute": ServicePricing(
        price=0.01344, unit=PricingUnit.GB_HOURS, provider="supabase",
        tier="pro", notes="$25/mo for ~1.86GB RAM"
    ),
    "supabase/storage": ServicePricing(
        price=0.021, unit=PricingUnit.GB_HOURS, provider="supabase",
        tier="pro", notes="$0.021/GB/month"
    ),
    "supabase/auth-mau": ServicePricing(
        price=0.00325, unit=PricingUnit.REQUESTS, provider="supabase",
        tier="pro", notes="$0.00325/MAU after 50K"
    ),
    "supabase/edge-functions": ServicePricing(
        price=0.000002, unit=PricingUnit.INVOCATIONS, provider="supabase",
        tier="pro", notes="$2/1M invocations"
    ),
    "supabase/realtime": ServicePricing(
        price=0.0000025, unit=PricingUnit.REQUESTS, provider="supabase",
        tier="pro", notes="$2.50/1M messages"
    ),

    # ==========================================================================
    # Vercel (Deployment & Edge)
    # https://vercel.com/pricing
    # ==========================================================================
    "vercel/serverless-functions": ServicePricing(
        price=0.00006, unit=PricingUnit.GB_HOURS, provider="vercel",
        tier="pro", notes="$0.18/GB-hr for execution"
    ),
    "vercel/edge-functions": ServicePricing(
        price=0.65, unit=PricingUnit.INVOCATIONS, provider="vercel",
        tier="pro", notes="$0.65/1M invocations"
    ),
    "vercel/bandwidth": ServicePricing(
        price=0.15, unit=PricingUnit.GB_HOURS, provider="vercel",
        tier="pro", notes="$0.15/GB after 1TB"
    ),
    "vercel/image-optimization": ServicePricing(
        price=5.00, unit=PricingUnit.REQUESTS, provider="vercel",
        tier="pro", notes="$5/1K source images"
    ),
}


def get_model_pricing(model_id: str) -> Optional[ModelPricing]:
    """
    Get pricing for a model by ID.

    Args:
        model_id: The model identifier (e.g., "claude-sonnet-4-5", "deepseek/deepseek-chat")

    Returns:
        ModelPricing dataclass or None if not found
    """
    return PROVIDER_PRICING.get(model_id)


def calculate_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """
    Calculate cost for a model invocation.

    Args:
        model_id: The model identifier
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Cost in USD

    Raises:
        ValueError: If model_id is not in the pricing registry
    """
    pricing = get_model_pricing(model_id)
    if pricing is None:
        raise ValueError(f"Unknown model: {model_id}. Add it to PROVIDER_PRICING.")

    input_cost = (input_tokens / 1_000_000) * pricing.input_price
    output_cost = (output_tokens / 1_000_000) * pricing.output_price
    return input_cost + output_cost


def get_cheapest_model(
    min_context: int = 0,
    providers: Optional[list[str]] = None,
    exclude_free: bool = True
) -> tuple[str, ModelPricing]:
    """
    Get the cheapest model matching criteria.

    Args:
        min_context: Minimum context window required
        providers: List of providers to consider (None = all)
        exclude_free: Exclude free models (usually have rate limits)

    Returns:
        Tuple of (model_id, pricing)
    """
    candidates = []

    for model_id, pricing in PROVIDER_PRICING.items():
        if pricing.context_window < min_context:
            continue
        if providers and pricing.provider not in providers:
            continue
        if exclude_free and pricing.input_price == 0 and pricing.output_price == 0:
            continue

        avg_cost = (pricing.input_price + pricing.output_price) / 2
        candidates.append((model_id, pricing, avg_cost))

    if not candidates:
        raise ValueError("No models match criteria")

    candidates.sort(key=lambda x: x[2])
    return candidates[0][0], candidates[0][1]


# =============================================================================
# SERVICE PRICING FUNCTIONS
# =============================================================================

def get_service_pricing(service_id: str) -> Optional[ServicePricing]:
    """
    Get pricing for a service by ID.

    Args:
        service_id: The service identifier (e.g., "cartesia/sonic-english")

    Returns:
        ServicePricing dataclass or None if not found
    """
    return SERVICE_PRICING.get(service_id)


def calculate_service_cost(
    service_id: str,
    quantity: float,
    unit: Optional[PricingUnit] = None,
) -> float:
    """
    Calculate cost for a service usage.

    Args:
        service_id: The service identifier
        quantity: Amount of usage (tokens, minutes, seconds, etc.)
        unit: Optional unit override (for validation)

    Returns:
        Cost in USD

    Raises:
        ValueError: If service_id not found or unit mismatch
    """
    pricing = get_service_pricing(service_id)
    if pricing is None:
        raise ValueError(f"Unknown service: {service_id}. Add it to SERVICE_PRICING.")

    if unit is not None and pricing.unit != unit:
        raise ValueError(
            f"Unit mismatch for {service_id}: expected {pricing.unit.value}, got {unit.value}"
        )

    return quantity * pricing.price


def calculate_audio_tts_cost(
    provider: str,
    characters: Optional[int] = None,
    seconds: Optional[float] = None,
) -> float:
    """
    Calculate TTS (text-to-speech) cost.

    Args:
        provider: Provider name ("cartesia", "elevenlabs")
        characters: Number of characters (for ElevenLabs)
        seconds: Duration in seconds (for Cartesia)

    Returns:
        Cost in USD
    """
    if provider == "cartesia":
        if seconds is None:
            raise ValueError("Cartesia requires seconds parameter")
        return calculate_service_cost("cartesia/sonic-english", seconds)

    elif provider == "elevenlabs":
        if characters is None:
            raise ValueError("ElevenLabs requires characters parameter")
        # ElevenLabs charges per 1M characters
        return calculate_service_cost("elevenlabs/multilingual-v2", characters / 1_000_000)

    else:
        raise ValueError(f"Unknown TTS provider: {provider}")


def calculate_audio_stt_cost(
    provider: str,
    minutes: Optional[float] = None,
    seconds: Optional[float] = None,
) -> float:
    """
    Calculate STT (speech-to-text) cost.

    Args:
        provider: Provider name ("deepgram", "assemblyai")
        minutes: Duration in minutes (for Deepgram)
        seconds: Duration in seconds (for AssemblyAI)

    Returns:
        Cost in USD
    """
    if provider == "deepgram":
        if minutes is None and seconds is not None:
            minutes = seconds / 60
        if minutes is None:
            raise ValueError("Deepgram requires minutes or seconds parameter")
        return calculate_service_cost("deepgram/nova-2", minutes)

    elif provider == "assemblyai":
        if seconds is None and minutes is not None:
            seconds = minutes * 60
        if seconds is None:
            raise ValueError("AssemblyAI requires seconds or minutes parameter")
        return calculate_service_cost("assemblyai/best", seconds)

    else:
        raise ValueError(f"Unknown STT provider: {provider}")


def get_all_providers() -> list[str]:
    """Get list of all unique providers."""
    providers = set()
    for pricing in PROVIDER_PRICING.values():
        providers.add(pricing.provider)
    for pricing in SERVICE_PRICING.values():
        providers.add(pricing.provider)
    return sorted(providers)
