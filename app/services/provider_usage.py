"""Service to fetch historical usage data from provider billing APIs.

Supports multiple API keys per provider for work/personal tracking.
"""

import os
from datetime import datetime, timedelta
from typing import Optional
import httpx
from pydantic import BaseModel


class UsageRecord(BaseModel):
    """Standardized usage record across providers."""
    provider: str
    account_label: str = "default"  # e.g., "work", "personal"
    date: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    model: Optional[str] = None
    request_count: int = 0


class ProviderBalance(BaseModel):
    """Current balance/credits for a provider."""
    provider: str
    account_label: str = "default"
    balance_usd: float
    usage_usd: float = 0.0
    limit_usd: Optional[float] = None


class AnthropicUsageService:
    """Fetch usage data from Anthropic Admin API.

    Requires Admin API key (different from regular API key).
    Docs: https://docs.anthropic.com/en/api/admin-api
    """

    BASE_URL = "https://api.anthropic.com/v1"

    def __init__(self, api_key: str, account_label: str = "default"):
        self.api_key = api_key
        self.account_label = account_label

    async def get_usage_report(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        group_by: str = "day"
    ) -> list[UsageRecord]:
        """Get usage report from Anthropic.

        Args:
            start_date: Start of reporting period (default: 30 days ago)
            end_date: End of reporting period (default: today)
            group_by: Grouping period - "day", "week", or "month"

        Returns:
            List of UsageRecord objects
        """
        if not start_date:
            start_date = datetime.now() - timedelta(days=30)
        if not end_date:
            end_date = datetime.now()

        url = f"{self.BASE_URL}/organizations/usage_report/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        params = {
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "group_by": group_by
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()

                records = []
                for entry in data.get("data", []):
                    records.append(UsageRecord(
                        provider="anthropic",
                        account_label=self.account_label,
                        date=entry.get("date", ""),
                        input_tokens=entry.get("input_tokens", 0),
                        output_tokens=entry.get("output_tokens", 0),
                        total_tokens=entry.get("input_tokens", 0) + entry.get("output_tokens", 0),
                        cost_usd=entry.get("cost_usd", 0.0),
                        model=entry.get("model"),
                        request_count=entry.get("request_count", 0)
                    ))
                return records

            except httpx.HTTPStatusError as e:
                if e.response.status_code in (401, 403):
                    # Regular API key - Admin API requires special Admin key
                    # Return empty list - use /stats for local tracking instead
                    return []
                raise
            except Exception:
                return []


class OpenRouterUsageService:
    """Fetch credits/usage from OpenRouter API.

    Docs: https://openrouter.ai/docs/api-reference
    """

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: str, account_label: str = "default"):
        self.api_key = api_key
        self.account_label = account_label

    async def get_credits(self) -> ProviderBalance:
        """Get current credits balance from OpenRouter."""
        url = f"{self.BASE_URL}/credits"
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

                # OpenRouter returns credits in USD
                return ProviderBalance(
                    provider="openrouter",
                    account_label=self.account_label,
                    balance_usd=data.get("data", {}).get("balance", 0.0),
                    usage_usd=data.get("data", {}).get("usage", 0.0),
                    limit_usd=data.get("data", {}).get("limit")
                )
            except httpx.HTTPError:
                return ProviderBalance(
                    provider="openrouter",
                    account_label=self.account_label,
                    balance_usd=0.0
                )


class ElevenLabsUsageService:
    """Fetch usage from ElevenLabs subscription API.

    Docs: https://elevenlabs.io/docs/api-reference/user/subscription/get
    """

    BASE_URL = "https://api.elevenlabs.io/v1"

    def __init__(self, api_key: str, account_label: str = "default"):
        self.api_key = api_key
        self.account_label = account_label

    async def get_subscription(self) -> ProviderBalance:
        """Get subscription info with character usage."""
        url = f"{self.BASE_URL}/user/subscription"
        headers = {"xi-api-key": self.api_key}

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

                # Calculate usage from character limits
                char_limit = data.get("character_limit", 0)
                char_used = data.get("character_count", 0)
                char_remaining = char_limit - char_used

                # ElevenLabs charges ~$0.30 per 1000 characters on Pro
                estimated_cost = (char_used / 1000) * 0.30

                return ProviderBalance(
                    provider="elevenlabs",
                    account_label=self.account_label,
                    balance_usd=0.0,  # Credit-based, not balance
                    usage_usd=estimated_cost,
                    limit_usd=None
                )
            except httpx.HTTPError:
                return ProviderBalance(
                    provider="elevenlabs",
                    account_label=self.account_label,
                    balance_usd=0.0
                )

    async def get_usage(self) -> list[UsageRecord]:
        """Get character usage as a usage record."""
        url = f"{self.BASE_URL}/user/subscription"
        headers = {"xi-api-key": self.api_key}

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

                char_used = data.get("character_count", 0)
                char_limit = data.get("character_limit", 0)

                return [UsageRecord(
                    provider="elevenlabs",
                    account_label=self.account_label,
                    date=datetime.now().strftime("%Y-%m-%d"),
                    total_tokens=char_used,  # Using tokens field for characters
                    cost_usd=(char_used / 1000) * 0.30,
                    request_count=0
                )]
            except httpx.HTTPError:
                return []


class DeepgramUsageService:
    """Fetch balance from Deepgram billing API.

    Docs: https://developers.deepgram.com/sdks-tools/sdks/python-sdk/billing/
    """

    BASE_URL = "https://api.deepgram.com/v1"

    def __init__(self, api_key: str, account_label: str = "default"):
        self.api_key = api_key
        self.account_label = account_label

    async def get_balances(self, project_id: str = None) -> ProviderBalance:
        """Get credit balance from Deepgram."""
        # Note: Requires project_id - would need to list projects first
        # For now, return a placeholder indicating the API is available
        return ProviderBalance(
            provider="deepgram",
            account_label=self.account_label,
            balance_usd=0.0,  # Would need project_id to fetch
            usage_usd=0.0,
            limit_usd=None
        )


class GroqUsageService:
    """Groq usage tracking - no billing API available yet.

    Note: There's a feature request for billing API:
    https://community.groq.com/t/add-api-endpoint-to-fetch-billing-and-usage-data/378
    """

    def __init__(self, api_key: str, account_label: str = "default"):
        self.api_key = api_key
        self.account_label = account_label

    async def get_usage(self) -> list[UsageRecord]:
        """Groq doesn't have a billing API - return empty."""
        return []


class MultiAccountUsageService:
    """Aggregate usage across multiple accounts per provider.

    Environment variables:
        ANTHROPIC_API_KEY - Default Anthropic key
        ANTHROPIC_API_KEY_WORK - Work Anthropic key (tim@coperniq.io)
        ANTHROPIC_API_KEY_PERSONAL - Personal key (tkipper@gmail.com)

        OPENROUTER_API_KEY - Default OpenRouter key
        OPENROUTER_API_KEY_WORK - Work OpenRouter key
        OPENROUTER_API_KEY_PERSONAL - Personal key

        Same pattern for all providers:
        - GOOGLE_API_KEY, CEREBRAS_API_KEY
        - ELEVENLABS_API_KEY, DEEPGRAM_API_KEY
        - GROQ_API_KEY, CARTESIA_API_KEY, ASSEMBLYAI_API_KEY
    """

    PROVIDERS = [
        "anthropic", "openrouter", "google", "cerebras",
        "elevenlabs", "deepgram", "groq", "cartesia", "assemblyai"
    ]
    ACCOUNT_LABELS = ["default", "work", "personal"]

    def __init__(self):
        self.accounts = self._discover_accounts()

    def _discover_accounts(self) -> dict:
        """Discover all configured API keys from environment."""
        accounts = {}

        for provider in self.PROVIDERS:
            provider_accounts = {}
            env_prefix = self._get_env_prefix(provider)

            # Check default key
            if key := os.getenv(f"{env_prefix}_API_KEY"):
                provider_accounts["default"] = key

            # Check labeled keys (work, personal)
            for label in ["WORK", "PERSONAL"]:
                if key := os.getenv(f"{env_prefix}_API_KEY_{label}"):
                    provider_accounts[label.lower()] = key

            if provider_accounts:
                accounts[provider] = provider_accounts

        return accounts

    def _get_env_prefix(self, provider: str) -> str:
        """Get environment variable prefix for provider."""
        prefixes = {
            "anthropic": "ANTHROPIC",
            "openrouter": "OPENROUTER",
            "google": "GOOGLE",
            "cerebras": "CEREBRAS",
            "gemini": "GOOGLE",
            "elevenlabs": "ELEVENLABS",
            "deepgram": "DEEPGRAM",
            "groq": "GROQ",
            "cartesia": "CARTESIA",
            "assemblyai": "ASSEMBLYAI"
        }
        return prefixes.get(provider, provider.upper())

    async def get_all_balances(self) -> list[ProviderBalance]:
        """Get balances from all configured accounts."""
        balances = []

        # OpenRouter balances
        for label, api_key in self.accounts.get("openrouter", {}).items():
            service = OpenRouterUsageService(api_key, label)
            balance = await service.get_credits()
            balances.append(balance)

        # ElevenLabs usage (character-based)
        for label, api_key in self.accounts.get("elevenlabs", {}).items():
            service = ElevenLabsUsageService(api_key, label)
            balance = await service.get_subscription()
            balances.append(balance)

        return balances

    async def get_all_usage(
        self,
        days: int = 30
    ) -> list[UsageRecord]:
        """Get usage history from all configured accounts."""
        records = []
        start_date = datetime.now() - timedelta(days=days)
        end_date = datetime.now()

        # Anthropic usage
        for label, api_key in self.accounts.get("anthropic", {}).items():
            service = AnthropicUsageService(api_key, label)
            account_records = await service.get_usage_report(start_date, end_date)
            records.extend(account_records)

        # ElevenLabs usage (character count)
        for label, api_key in self.accounts.get("elevenlabs", {}).items():
            service = ElevenLabsUsageService(api_key, label)
            account_records = await service.get_usage()
            records.extend(account_records)

        return records

    def get_configured_accounts(self) -> dict:
        """Return list of configured accounts (without exposing keys)."""
        return {
            provider: list(accounts.keys())
            for provider, accounts in self.accounts.items()
        }


async def get_all_provider_usage(days: int = 30) -> dict:
    """Fetch usage data from all configured providers and accounts.

    Returns dict with:
        - configured_accounts: Which accounts are set up per provider
        - balances: Current balance for providers with credit systems
        - usage_history: Historical usage from providers with billing APIs
        - local_tracking: Usage tracked through this optimizer
        - errors: Any errors encountered
    """
    service = MultiAccountUsageService()

    results = {
        "configured_accounts": service.get_configured_accounts(),
        "balances": [],
        "usage_history": [],
        "local_tracking": {
            "note": "See /stats endpoint for usage tracked through this optimizer"
        },
        "errors": []
    }

    # Get balances
    try:
        balances = await service.get_all_balances()
        results["balances"] = [b.model_dump() for b in balances]
    except Exception as e:
        results["errors"].append({"operation": "get_balances", "error": str(e)})

    # Get usage history
    try:
        usage = await service.get_all_usage(days)
        results["usage_history"] = [r.model_dump() for r in usage]
    except Exception as e:
        results["errors"].append({"operation": "get_usage", "error": str(e)})

    return results
