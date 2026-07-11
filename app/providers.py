"""LLM provider implementations for Gemini, Claude, Cerebras, Groq, Together AI, OpenRouter, Mistral, Cohere, Ollama, Fireworks, and Bedrock."""
import os
from typing import Tuple
import httpx


class ProviderError(Exception):
    """Base exception for provider errors."""
    pass


class GeminiProvider:
    """Google Gemini provider using direct API."""

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
    MODEL = "gemini-1.5-flash"

    # Pricing per 1M tokens (as of 2024)
    INPUT_PRICE = 0.075  # $0.075 per 1M input tokens
    OUTPUT_PRICE = 0.30  # $0.30 per 1M output tokens

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def complete(self, prompt: str, max_tokens: int = 1000) -> Tuple[str, int, int, float]:
        """
        Send completion request to Gemini.

        Returns:
            Tuple of (response_text, input_tokens, output_tokens, cost)
        """
        url = f"{self.BASE_URL}/models/{self.MODEL}:generateContent?key={self.api_key}"

        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": 0.7
            }
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

                # Extract response text
                if "candidates" not in data or not data["candidates"]:
                    raise ProviderError("No response from Gemini")

                text = data["candidates"][0]["content"]["parts"][0]["text"]

                # Extract token usage
                usage = data.get("usageMetadata", {})
                input_tokens = usage.get("promptTokenCount", 0)
                output_tokens = usage.get("candidatesTokenCount", 0)

                # Calculate cost
                cost = self.calculate_cost(input_tokens, output_tokens)

                return text, input_tokens, output_tokens, cost

            except httpx.HTTPError as e:
                raise ProviderError(f"Gemini API error: {str(e)}")

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost based on token usage."""
        input_cost = (input_tokens / 1_000_000) * self.INPUT_PRICE
        output_cost = (output_tokens / 1_000_000) * self.OUTPUT_PRICE
        return input_cost + output_cost


class ClaudeProvider:
    """Anthropic Claude provider using direct API."""

    BASE_URL = "https://api.anthropic.com/v1"
    MODEL = "claude-3-haiku-20240307"

    # Pricing per 1M tokens
    INPUT_PRICE = 0.25   # $0.25 per 1M input tokens
    OUTPUT_PRICE = 1.25  # $1.25 per 1M output tokens

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def complete(self, prompt: str, max_tokens: int = 1000) -> Tuple[str, int, int, float]:
        """
        Send completion request to Claude.

        Returns:
            Tuple of (response_text, input_tokens, output_tokens, cost)
        """
        url = f"{self.BASE_URL}/messages"

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        payload = {
            "model": self.MODEL,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()

                # Extract response text
                text = data["content"][0]["text"]

                # Extract token usage
                usage = data["usage"]
                input_tokens = usage["input_tokens"]
                output_tokens = usage["output_tokens"]

                # Calculate cost
                cost = self.calculate_cost(input_tokens, output_tokens)

                return text, input_tokens, output_tokens, cost

            except httpx.HTTPError as e:
                raise ProviderError(f"Claude API error: {str(e)}")

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost based on token usage."""
        input_cost = (input_tokens / 1_000_000) * self.INPUT_PRICE
        output_cost = (output_tokens / 1_000_000) * self.OUTPUT_PRICE
        return input_cost + output_cost


class OpenRouterProvider:
    """OpenRouter provider for fallback and alternative models (NO OpenAI models)."""

    BASE_URL = "https://openrouter.ai/api/v1"
    MODEL = "meta-llama/llama-3.1-8b-instruct:free"  # Default: free Llama model

    # Model-specific pricing (per 1M tokens)
    MODEL_PRICING = {
        "meta-llama/llama-3.1-8b-instruct:free": {"input": 0.0, "output": 0.0},
        "google/gemini-flash-1.5": {"input": 0.075, "output": 0.30},
        "anthropic/claude-3-haiku": {"input": 0.25, "output": 1.25},
        "anthropic/claude-3.5-sonnet": {"input": 3.00, "output": 15.00},
    }

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def complete(self, model: str, prompt: str, max_tokens: int = 1000) -> Tuple[str, int, int, float]:
        """
        Send completion request to OpenRouter.

        Args:
            model: Model identifier (e.g., "google/gemini-flash-1.5")
            prompt: User prompt
            max_tokens: Maximum response tokens

        Returns:
            Tuple of (response_text, input_tokens, output_tokens, cost)
        """
        url = f"{self.BASE_URL}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()

                # Extract response text
                text = data["choices"][0]["message"]["content"]

                # Extract token usage
                usage = data["usage"]
                input_tokens = usage["prompt_tokens"]
                output_tokens = usage["completion_tokens"]

                # Calculate cost
                cost = self.calculate_cost(model, input_tokens, output_tokens)

                return text, input_tokens, output_tokens, cost

            except httpx.HTTPError as e:
                raise ProviderError(f"OpenRouter API error: {str(e)}")

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost based on model and token usage."""
        pricing = self.MODEL_PRICING.get(model, {"input": 0, "output": 0})
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost


class CerebrasProvider:
    """Cerebras provider - fastest inference (1000+ tokens/sec)."""

    BASE_URL = "https://api.cerebras.ai/v1"
    MODEL = "llama3.1-8b"  # Default to fastest, cheapest model

    # Pricing per 1M tokens
    MODEL_PRICING = {
        "llama3.1-8b": {"input": 0.10, "output": 0.10},
        "llama3.1-70b": {"input": 0.60, "output": 0.60},
    }

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def complete(self, prompt: str, max_tokens: int = 1000, model: str = None) -> Tuple[str, int, int, float]:
        """
        Send completion request to Cerebras.

        Returns:
            Tuple of (response_text, input_tokens, output_tokens, cost)
        """
        url = f"{self.BASE_URL}/chat/completions"
        model = model or self.MODEL

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.7
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

                # Extract response text
                text = data["choices"][0]["message"]["content"]

                # Extract token usage
                usage = data["usage"]
                input_tokens = usage["prompt_tokens"]
                output_tokens = usage["completion_tokens"]

                # Calculate cost
                cost = self.calculate_cost(model, input_tokens, output_tokens)

                return text, input_tokens, output_tokens, cost

            except httpx.HTTPError as e:
                raise ProviderError(f"Cerebras API error: {str(e)}")

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost based on model and token usage."""
        pricing = self.MODEL_PRICING.get(model, {"input": 0.10, "output": 0.10})
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost


class GroqProvider:
    """Groq provider - ultra-fast LPU inference."""

    BASE_URL = "https://api.groq.com/openai/v1"
    MODEL = "llama-3.3-70b-versatile"  # Default model

    # Pricing per 1M tokens (as of Dec 2024)
    MODEL_PRICING = {
        "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
        "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
        "llama-3.2-90b-vision-preview": {"input": 0.90, "output": 0.90},
        "mixtral-8x7b-32768": {"input": 0.24, "output": 0.24},
        "gemma2-9b-it": {"input": 0.20, "output": 0.20},
    }

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def complete(self, prompt: str, max_tokens: int = 1000, model: str = None) -> Tuple[str, int, int, float]:
        """
        Send completion request to Groq.

        Returns:
            Tuple of (response_text, input_tokens, output_tokens, cost)
        """
        url = f"{self.BASE_URL}/chat/completions"
        model = model or self.MODEL

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.7
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

                # Extract response text
                text = data["choices"][0]["message"]["content"]

                # Extract token usage
                usage = data["usage"]
                input_tokens = usage["prompt_tokens"]
                output_tokens = usage["completion_tokens"]

                # Calculate cost
                cost = self.calculate_cost(model, input_tokens, output_tokens)

                return text, input_tokens, output_tokens, cost

            except httpx.HTTPError as e:
                raise ProviderError(f"Groq API error: {str(e)}")

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost based on model and token usage."""
        pricing = self.MODEL_PRICING.get(model, {"input": 0.59, "output": 0.79})
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost


class TogetherAIProvider:
    """Together AI provider - run fine-tuned models (Unsloth, custom LoRAs)."""

    BASE_URL = "https://api.together.xyz/v1"
    MODEL = "meta-llama/Llama-3.2-3B-Instruct-Turbo"  # Default fast model

    # Pricing per 1M tokens
    MODEL_PRICING = {
        # Llama 3.2 models
        "meta-llama/Llama-3.2-3B-Instruct-Turbo": {"input": 0.06, "output": 0.06},
        "meta-llama/Llama-3.2-11B-Vision-Instruct-Turbo": {"input": 0.18, "output": 0.18},
        "meta-llama/Llama-3.2-90B-Vision-Instruct-Turbo": {"input": 0.88, "output": 0.88},
        # Llama 3.1 models
        "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo": {"input": 0.18, "output": 0.18},
        "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo": {"input": 0.88, "output": 0.88},
        "meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo": {"input": 3.50, "output": 3.50},
        # Mixtral/Mistral
        "mistralai/Mixtral-8x7B-Instruct-v0.1": {"input": 0.60, "output": 0.60},
        "mistralai/Mistral-7B-Instruct-v0.3": {"input": 0.20, "output": 0.20},
        # Fine-tuned models (custom - charged at base rate)
        "custom": {"input": 0.20, "output": 0.20},
    }

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def complete(self, prompt: str, max_tokens: int = 1000, model: str = None) -> Tuple[str, int, int, float]:
        """
        Send completion request to Together AI.

        Args:
            prompt: User prompt
            max_tokens: Maximum response tokens
            model: Model ID (can be fine-tuned model endpoint)

        Returns:
            Tuple of (response_text, input_tokens, output_tokens, cost)
        """
        url = f"{self.BASE_URL}/chat/completions"
        model = model or self.MODEL

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.7
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

                # Extract response text
                text = data["choices"][0]["message"]["content"]

                # Extract token usage
                usage = data["usage"]
                input_tokens = usage["prompt_tokens"]
                output_tokens = usage["completion_tokens"]

                # Calculate cost
                cost = self.calculate_cost(model, input_tokens, output_tokens)

                return text, input_tokens, output_tokens, cost

            except httpx.HTTPError as e:
                raise ProviderError(f"Together AI API error: {str(e)}")

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost based on model and token usage."""
        # Check if it's a known model, otherwise use custom pricing
        pricing = self.MODEL_PRICING.get(model, self.MODEL_PRICING["custom"])
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost


class MistralProvider:
    """Mistral AI provider - European LLM with strong multilingual support."""

    BASE_URL = "https://api.mistral.ai/v1/chat/completions"
    MODEL = "mistral-small-latest"  # Default: cheapest production model

    # Pricing per 1M tokens (Dec 2025)
    MODEL_PRICING = {
        "mistral-small-latest": {"input": 0.10, "output": 0.30},
        "mistral-medium-latest": {"input": 0.27, "output": 0.81},
        "mistral-large-latest": {"input": 2.00, "output": 6.00},
        "codestral-latest": {"input": 0.30, "output": 0.90},
        "open-mistral-nemo": {"input": 0.15, "output": 0.15},
        "ministral-3b-latest": {"input": 0.04, "output": 0.04},
        "ministral-8b-latest": {"input": 0.10, "output": 0.10},
    }

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def complete(self, prompt: str, max_tokens: int = 1000, model: str = None) -> Tuple[str, int, int, float]:
        """
        Send completion request to Mistral AI.

        Returns:
            Tuple of (response_text, input_tokens, output_tokens, cost)
        """
        model = model or self.MODEL

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.7
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(self.BASE_URL, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

                # Extract response text
                text = data["choices"][0]["message"]["content"]

                # Extract token usage
                usage = data["usage"]
                input_tokens = usage["prompt_tokens"]
                output_tokens = usage["completion_tokens"]

                # Calculate cost
                cost = self.calculate_cost(model, input_tokens, output_tokens)

                return text, input_tokens, output_tokens, cost

            except httpx.HTTPError as e:
                raise ProviderError(f"Mistral API error: {str(e)}")

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost based on model and token usage."""
        pricing = self.MODEL_PRICING.get(model, {"input": 0.10, "output": 0.30})
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost


class FireworksProvider:
    """Fireworks AI provider - fast serverless inference for open models."""

    BASE_URL = "https://api.fireworks.ai/inference/v1/chat/completions"
    MODEL = "accounts/fireworks/models/llama-v3p1-70b-instruct"  # Default model

    # Pricing per 1M tokens (Dec 2025)
    MODEL_PRICING = {
        "accounts/fireworks/models/llama-v3p1-70b-instruct": {"input": 0.90, "output": 0.90},
        "accounts/fireworks/models/llama-v3p1-8b-instruct": {"input": 0.20, "output": 0.20},
        "accounts/fireworks/models/llama-v3p2-3b-instruct": {"input": 0.10, "output": 0.10},
        "accounts/fireworks/models/mixtral-8x7b-instruct": {"input": 0.50, "output": 0.50},
        "accounts/fireworks/models/mixtral-8x22b-instruct": {"input": 0.90, "output": 0.90},
        "accounts/fireworks/models/qwen2p5-72b-instruct": {"input": 0.90, "output": 0.90},
    }

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def complete(self, prompt: str, max_tokens: int = 1000, model: str = None) -> Tuple[str, int, int, float]:
        """
        Send completion request to Fireworks AI.

        Returns:
            Tuple of (response_text, input_tokens, output_tokens, cost)
        """
        model = model or self.MODEL

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.7
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(self.BASE_URL, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

                # Extract response text
                text = data["choices"][0]["message"]["content"]

                # Extract token usage
                usage = data["usage"]
                input_tokens = usage["prompt_tokens"]
                output_tokens = usage["completion_tokens"]

                # Calculate cost
                cost = self.calculate_cost(model, input_tokens, output_tokens)

                return text, input_tokens, output_tokens, cost

            except httpx.HTTPError as e:
                raise ProviderError(f"Fireworks API error: {str(e)}")

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost based on model and token usage."""
        pricing = self.MODEL_PRICING.get(model, {"input": 0.90, "output": 0.90})
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost


class CohereProvider:
    """Cohere provider - enterprise NLP with excellent embeddings and RAG."""

    BASE_URL = "https://api.cohere.ai/v1/chat"
    MODEL = "command-r"  # Default: balanced cost/performance

    # Pricing per 1M tokens (Dec 2025)
    MODEL_PRICING = {
        "command-r-plus": {"input": 2.50, "output": 10.00},
        "command-r": {"input": 0.15, "output": 0.60},
        "command-light": {"input": 0.03, "output": 0.06},
        "command-r-08-2024": {"input": 0.15, "output": 0.60},
        "command-r-plus-08-2024": {"input": 2.50, "output": 10.00},
    }

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def complete(self, prompt: str, max_tokens: int = 1000, model: str = None) -> Tuple[str, int, int, float]:
        """
        Send completion request to Cohere.

        Note: Cohere uses a different API format than OpenAI-compatible endpoints.

        Returns:
            Tuple of (response_text, input_tokens, output_tokens, cost)
        """
        model = model or self.MODEL

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Cohere uses 'message' not 'messages' array
        payload = {
            "model": model,
            "message": prompt,
            "max_tokens": max_tokens,
            "temperature": 0.7
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(self.BASE_URL, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

                # Cohere returns 'text' directly
                text = data["text"]

                # Extract token usage from meta
                meta = data.get("meta", {})
                tokens = meta.get("tokens", {})
                input_tokens = tokens.get("input_tokens", 0)
                output_tokens = tokens.get("output_tokens", 0)

                # Calculate cost
                cost = self.calculate_cost(model, input_tokens, output_tokens)

                return text, input_tokens, output_tokens, cost

            except httpx.HTTPError as e:
                raise ProviderError(f"Cohere API error: {str(e)}")

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost based on model and token usage."""
        pricing = self.MODEL_PRICING.get(model, {"input": 0.15, "output": 0.60})
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost


class OllamaProvider:
    """Ollama provider - local LLM inference (free, no API key needed)."""

    MODEL = "llama3.2"  # Default local model
    INPUT_PRICE = 0.0   # Free (local inference)
    OUTPUT_PRICE = 0.0

    def __init__(self, host: str = None):
        """
        Initialize Ollama provider.

        Args:
            host: Ollama server URL (default: http://localhost:11434)
        """
        self.base_url = host or os.getenv("OLLAMA_HOST", "http://localhost:11434")

    async def complete(self, prompt: str, max_tokens: int = 1000, model: str = None) -> Tuple[str, int, int, float]:
        """
        Send completion request to local Ollama server.

        Returns:
            Tuple of (response_text, input_tokens, output_tokens, cost=0.0)
        """
        model = model or self.MODEL
        url = f"{self.base_url}/api/chat"

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.7
            }
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

                # Extract response text
                text = data["message"]["content"]

                # Ollama provides token counts
                input_tokens = data.get("prompt_eval_count", 0)
                output_tokens = data.get("eval_count", 0)

                # Local inference is free
                cost = 0.0

                return text, input_tokens, output_tokens, cost

            except httpx.HTTPError as e:
                raise ProviderError(f"Ollama API error: {str(e)}")

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Local inference is always free."""
        return 0.0

    @staticmethod
    def is_available() -> bool:
        """Check if Ollama server is running locally."""
        import socket
        host = os.getenv("OLLAMA_HOST", "localhost")
        port = 11434
        try:
            # Extract host/port if full URL provided
            if "://" in host:
                from urllib.parse import urlparse
                parsed = urlparse(host)
                host = parsed.hostname or "localhost"
                port = parsed.port or 11434

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False


class BedrockProvider:
    """AWS Bedrock provider - Claude and other models on AWS infrastructure."""

    MODEL = "anthropic.claude-3-haiku-20240307-v1:0"  # Default: cheapest Claude

    # Pricing per 1M tokens (AWS Bedrock, Dec 2025)
    MODEL_PRICING = {
        # Claude 3 models
        "anthropic.claude-3-haiku-20240307-v1:0": {"input": 0.25, "output": 1.25},
        "anthropic.claude-3-sonnet-20240229-v1:0": {"input": 3.00, "output": 15.00},
        "anthropic.claude-3-opus-20240229-v1:0": {"input": 15.00, "output": 75.00},
        # Claude 3.5 models
        "anthropic.claude-3-5-sonnet-20240620-v1:0": {"input": 3.00, "output": 15.00},
        "anthropic.claude-3-5-sonnet-20241022-v2:0": {"input": 3.00, "output": 15.00},
        # Llama models
        "meta.llama3-8b-instruct-v1:0": {"input": 0.30, "output": 0.60},
        "meta.llama3-70b-instruct-v1:0": {"input": 2.65, "output": 3.50},
        # Mistral models
        "mistral.mistral-7b-instruct-v0:2": {"input": 0.15, "output": 0.20},
        "mistral.mixtral-8x7b-instruct-v0:1": {"input": 0.45, "output": 0.70},
    }

    def __init__(self, region: str = None):
        """
        Initialize Bedrock provider using AWS credentials from environment.

        Args:
            region: AWS region (default: from AWS_REGION env var or us-east-1)
        """
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        self._client = None

    def _get_client(self):
        """Lazy-load boto3 client."""
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client(
                    "bedrock-runtime",
                    region_name=self.region
                )
            except ImportError:
                raise ProviderError("boto3 not installed. Run: pip install boto3")
        return self._client

    async def complete(self, prompt: str, max_tokens: int = 1000, model: str = None) -> Tuple[str, int, int, float]:
        """
        Send completion request to AWS Bedrock.

        Returns:
            Tuple of (response_text, input_tokens, output_tokens, cost)
        """
        import json
        import asyncio

        model = model or self.MODEL
        client = self._get_client()

        # Format depends on model provider
        if model.startswith("anthropic."):
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}]
            }
        elif model.startswith("meta."):
            body = {
                "prompt": f"<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\n{prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n",
                "max_gen_len": max_tokens,
                "temperature": 0.7
            }
        elif model.startswith("mistral."):
            body = {
                "prompt": f"<s>[INST] {prompt} [/INST]",
                "max_tokens": max_tokens,
                "temperature": 0.7
            }
        else:
            raise ProviderError(f"Unsupported Bedrock model: {model}")

        try:
            # Run sync boto3 call in thread pool
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.invoke_model(
                    modelId=model,
                    body=json.dumps(body),
                    contentType="application/json",
                    accept="application/json"
                )
            )

            result = json.loads(response["body"].read())

            # Parse response based on model provider
            if model.startswith("anthropic."):
                text = result["content"][0]["text"]
                input_tokens = result["usage"]["input_tokens"]
                output_tokens = result["usage"]["output_tokens"]
            elif model.startswith("meta."):
                text = result["generation"]
                input_tokens = result.get("prompt_token_count", 0)
                output_tokens = result.get("generation_token_count", 0)
            elif model.startswith("mistral."):
                text = result["outputs"][0]["text"]
                # Mistral on Bedrock doesn't return token counts, estimate
                input_tokens = len(prompt.split()) * 1.3
                output_tokens = len(text.split()) * 1.3

            cost = self.calculate_cost(model, int(input_tokens), int(output_tokens))
            return text, int(input_tokens), int(output_tokens), cost

        except Exception as e:
            raise ProviderError(f"Bedrock API error: {str(e)}")

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost based on model and token usage."""
        pricing = self.MODEL_PRICING.get(model, {"input": 0.25, "output": 1.25})
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost


class DeepSeekProvider:
    """DeepSeek provider - cheap, capable OpenAI-compatible models."""

    BASE_URL = "https://api.deepseek.com/v1"
    MODEL = "deepseek-chat"  # Default: general chat; deepseek-reasoner also available

    # PLACEHOLDER pricing — verify against vendor pricing pages before billing goes live
    # Pricing per 1M tokens
    MODEL_PRICING = {
        "deepseek-chat": {"input": 0.27, "output": 1.10},
        "deepseek-reasoner": {"input": 0.55, "output": 2.19},
    }

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def complete(self, prompt: str, max_tokens: int = 1000, model: str = None) -> Tuple[str, int, int, float]:
        """
        Send completion request to DeepSeek.

        Returns:
            Tuple of (response_text, input_tokens, output_tokens, cost)
        """
        url = f"{self.BASE_URL}/chat/completions"
        model = model or self.MODEL

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.7
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

                text = data["choices"][0]["message"]["content"]

                usage = data["usage"]
                input_tokens = usage["prompt_tokens"]
                output_tokens = usage["completion_tokens"]

                cost = self.calculate_cost(model, input_tokens, output_tokens)

                return text, input_tokens, output_tokens, cost

            except httpx.HTTPError as e:
                raise ProviderError(f"DeepSeek API error: {str(e)}")

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost based on model and token usage."""
        pricing = self.MODEL_PRICING.get(model, {"input": 0.27, "output": 1.10})
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost


class GLMProvider:
    """GLM (Zhipu BigModel) provider - agentic-strong OpenAI-compatible models."""

    # China endpoint. International alternative: https://api.z.ai/api/paas/v4
    # (pending account-region confirmation — no API key exists yet to test either)
    BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
    MODEL = "glm-4.7"  # Default flagship model

    # PLACEHOLDER pricing — verify against vendor pricing pages before billing goes live
    # Pricing per 1M tokens
    MODEL_PRICING = {
        "glm-4.7": {"input": 0.60, "output": 2.20},
    }

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def complete(self, prompt: str, max_tokens: int = 1000, model: str = None) -> Tuple[str, int, int, float]:
        """
        Send completion request to GLM (Zhipu).

        Returns:
            Tuple of (response_text, input_tokens, output_tokens, cost)
        """
        url = f"{self.BASE_URL}/chat/completions"
        model = model or self.MODEL

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.7
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

                text = data["choices"][0]["message"]["content"]

                usage = data["usage"]
                input_tokens = usage["prompt_tokens"]
                output_tokens = usage["completion_tokens"]

                cost = self.calculate_cost(model, input_tokens, output_tokens)

                return text, input_tokens, output_tokens, cost

            except httpx.HTTPError as e:
                raise ProviderError(f"GLM API error: {str(e)}")

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost based on model and token usage."""
        pricing = self.MODEL_PRICING.get(model, {"input": 0.60, "output": 2.20})
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost


class QwenProvider:
    """Qwen (Alibaba DashScope) provider - cheap, capable OpenAI-compatible models."""

    BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    MODEL = "qwen-plus"  # Default balanced model

    # PLACEHOLDER pricing — verify against vendor pricing pages before billing goes live
    # Pricing per 1M tokens
    MODEL_PRICING = {
        "qwen-plus": {"input": 0.40, "output": 1.20},
        "qwen-turbo": {"input": 0.05, "output": 0.20},
        "qwen-max": {"input": 1.60, "output": 6.40},
    }

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def complete(self, prompt: str, max_tokens: int = 1000, model: str = None) -> Tuple[str, int, int, float]:
        """
        Send completion request to Qwen (DashScope).

        Returns:
            Tuple of (response_text, input_tokens, output_tokens, cost)
        """
        url = f"{self.BASE_URL}/chat/completions"
        model = model or self.MODEL

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.7
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

                text = data["choices"][0]["message"]["content"]

                usage = data["usage"]
                input_tokens = usage["prompt_tokens"]
                output_tokens = usage["completion_tokens"]

                cost = self.calculate_cost(model, input_tokens, output_tokens)

                return text, input_tokens, output_tokens, cost

            except httpx.HTTPError as e:
                raise ProviderError(f"Qwen API error: {str(e)}")

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost based on model and token usage."""
        pricing = self.MODEL_PRICING.get(model, {"input": 0.40, "output": 1.20})
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost


def init_providers() -> dict:
    """
    Initialize available providers based on environment variables.

    Supported providers:
    - gemini: Google Gemini (GOOGLE_API_KEY)
    - claude: Anthropic Claude (ANTHROPIC_API_KEY)
    - cerebras: Ultra-fast inference (CEREBRAS_API_KEY)
    - groq: LPU inference (GROQ_API_KEY)
    - together: Fine-tuned models (TOGETHER_API_KEY)
    - mistral: European LLM (MISTRAL_API_KEY)
    - fireworks: Fast serverless (FIREWORKS_API_KEY)
    - cohere: Enterprise NLP (COHERE_API_KEY)
    - ollama: Local inference (OLLAMA_HOST, no key needed)
    - bedrock: AWS Bedrock (AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY)
    - openrouter: Multi-model gateway (OPENROUTER_API_KEY)

    Returns:
        Dictionary of {provider_name: provider_instance}
    """
    providers = {}

    # Primary providers
    if api_key := os.getenv("GOOGLE_API_KEY"):
        providers["gemini"] = GeminiProvider(api_key)

    if api_key := os.getenv("ANTHROPIC_API_KEY"):
        providers["claude"] = ClaudeProvider(api_key)

    # Ultra-fast providers
    if api_key := os.getenv("CEREBRAS_API_KEY"):
        providers["cerebras"] = CerebrasProvider(api_key)

    if api_key := os.getenv("GROQ_API_KEY"):
        providers["groq"] = GroqProvider(api_key)

    # Fine-tuned model hosting (Unsloth, custom LoRAs)
    if api_key := os.getenv("TOGETHER_API_KEY"):
        providers["together"] = TogetherAIProvider(api_key)

    # New providers - Technical Depth Sprint
    if api_key := os.getenv("MISTRAL_API_KEY"):
        providers["mistral"] = MistralProvider(api_key)

    if api_key := os.getenv("FIREWORKS_API_KEY"):
        providers["fireworks"] = FireworksProvider(api_key)

    if api_key := os.getenv("COHERE_API_KEY"):
        providers["cohere"] = CohereProvider(api_key)

    # Cheap + capable Chinese frontier providers (OpenAI-compatible)
    if api_key := os.getenv("DEEPSEEK_API_KEY"):
        providers["deepseek"] = DeepSeekProvider(api_key)

    if api_key := os.getenv("GLM_API_KEY"):
        providers["glm"] = GLMProvider(api_key)

    if api_key := os.getenv("DASHSCOPE_API_KEY"):
        providers["qwen"] = QwenProvider(api_key)

    # Ollama - local inference (no API key needed)
    if OllamaProvider.is_available():
        providers["ollama"] = OllamaProvider()

    # AWS Bedrock - requires AWS credentials
    if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
        providers["bedrock"] = BedrockProvider()

    # Fallback aggregator (NO OpenAI models)
    if api_key := os.getenv("OPENROUTER_API_KEY"):
        providers["openrouter"] = OpenRouterProvider(api_key)

    return providers
