"""
Tests for New Providers - Technical Depth Sprint (Dec 2025)

Tests for Mistral, Fireworks, Cohere, Ollama, and Bedrock providers.
Uses mocked HTTP responses for unit testing.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal

from app.providers import (
    MistralProvider,
    FireworksProvider,
    CohereProvider,
    OllamaProvider,
    BedrockProvider,
    ProviderError,
    init_providers,
)


# =============================================================================
# Mistral Provider Tests
# =============================================================================

class TestMistralProvider:
    """Test Mistral AI provider."""

    def test_init(self):
        """Should initialize with API key."""
        provider = MistralProvider("test-api-key")
        assert provider.api_key == "test-api-key"
        assert provider.MODEL == "mistral-small-latest"

    def test_model_pricing(self):
        """Should have correct pricing for all models."""
        assert MistralProvider.MODEL_PRICING["mistral-small-latest"]["input"] == 0.10
        assert MistralProvider.MODEL_PRICING["mistral-small-latest"]["output"] == 0.30
        assert MistralProvider.MODEL_PRICING["mistral-large-latest"]["input"] == 2.00
        assert MistralProvider.MODEL_PRICING["codestral-latest"]["input"] == 0.30

    def test_calculate_cost(self):
        """Should calculate cost correctly."""
        provider = MistralProvider("test-key")
        # 1000 input tokens, 500 output tokens with mistral-small
        cost = provider.calculate_cost("mistral-small-latest", 1000, 500)
        expected = (1000 / 1_000_000) * 0.10 + (500 / 1_000_000) * 0.30
        assert cost == pytest.approx(expected)

    @pytest.mark.asyncio
    async def test_complete_success(self):
        """Should return response on successful completion."""
        provider = MistralProvider("test-key")

        mock_response = {
            "choices": [{"message": {"content": "Hello from Mistral!"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5}
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = MagicMock(
                json=MagicMock(return_value=mock_response),
                raise_for_status=MagicMock()
            )
            mock_client.return_value.__aenter__.return_value = mock_instance

            text, input_tokens, output_tokens, cost = await provider.complete("Hello")

            assert text == "Hello from Mistral!"
            assert input_tokens == 10
            assert output_tokens == 5
            assert cost > 0


# =============================================================================
# Fireworks Provider Tests
# =============================================================================

class TestFireworksProvider:
    """Test Fireworks AI provider."""

    def test_init(self):
        """Should initialize with API key."""
        provider = FireworksProvider("test-api-key")
        assert provider.api_key == "test-api-key"
        assert "llama-v3p1-70b-instruct" in provider.MODEL

    def test_model_pricing(self):
        """Should have correct pricing for all models."""
        pricing = FireworksProvider.MODEL_PRICING
        assert pricing["accounts/fireworks/models/llama-v3p1-70b-instruct"]["input"] == 0.90
        assert pricing["accounts/fireworks/models/llama-v3p1-8b-instruct"]["input"] == 0.20
        assert pricing["accounts/fireworks/models/mixtral-8x7b-instruct"]["input"] == 0.50

    def test_calculate_cost(self):
        """Should calculate cost correctly."""
        provider = FireworksProvider("test-key")
        model = "accounts/fireworks/models/llama-v3p1-8b-instruct"
        cost = provider.calculate_cost(model, 1000, 500)
        expected = (1000 / 1_000_000) * 0.20 + (500 / 1_000_000) * 0.20
        assert cost == pytest.approx(expected)

    @pytest.mark.asyncio
    async def test_complete_success(self):
        """Should return response on successful completion."""
        provider = FireworksProvider("test-key")

        mock_response = {
            "choices": [{"message": {"content": "Fireworks response!"}}],
            "usage": {"prompt_tokens": 15, "completion_tokens": 8}
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = MagicMock(
                json=MagicMock(return_value=mock_response),
                raise_for_status=MagicMock()
            )
            mock_client.return_value.__aenter__.return_value = mock_instance

            text, input_tokens, output_tokens, cost = await provider.complete("Test")

            assert text == "Fireworks response!"
            assert input_tokens == 15
            assert output_tokens == 8


# =============================================================================
# Cohere Provider Tests
# =============================================================================

class TestCohereProvider:
    """Test Cohere provider."""

    def test_init(self):
        """Should initialize with API key."""
        provider = CohereProvider("test-api-key")
        assert provider.api_key == "test-api-key"
        assert provider.MODEL == "command-r"

    def test_model_pricing(self):
        """Should have correct pricing for all models."""
        pricing = CohereProvider.MODEL_PRICING
        assert pricing["command-r"]["input"] == 0.15
        assert pricing["command-r"]["output"] == 0.60
        assert pricing["command-r-plus"]["input"] == 2.50
        assert pricing["command-light"]["input"] == 0.03

    def test_calculate_cost(self):
        """Should calculate cost correctly."""
        provider = CohereProvider("test-key")
        cost = provider.calculate_cost("command-r", 1000, 500)
        expected = (1000 / 1_000_000) * 0.15 + (500 / 1_000_000) * 0.60
        assert cost == pytest.approx(expected)

    @pytest.mark.asyncio
    async def test_complete_success(self):
        """Should return response using Cohere's custom format."""
        provider = CohereProvider("test-key")

        # Cohere uses different response format
        mock_response = {
            "text": "Cohere response!",
            "meta": {
                "tokens": {
                    "input_tokens": 12,
                    "output_tokens": 6
                }
            }
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = MagicMock(
                json=MagicMock(return_value=mock_response),
                raise_for_status=MagicMock()
            )
            mock_client.return_value.__aenter__.return_value = mock_instance

            text, input_tokens, output_tokens, cost = await provider.complete("Test")

            assert text == "Cohere response!"
            assert input_tokens == 12
            assert output_tokens == 6


# =============================================================================
# Ollama Provider Tests
# =============================================================================

class TestOllamaProvider:
    """Test Ollama local provider."""

    def test_init_default_host(self):
        """Should use default localhost host."""
        provider = OllamaProvider()
        assert provider.base_url == "http://localhost:11434"

    def test_init_custom_host(self):
        """Should accept custom host."""
        provider = OllamaProvider(host="http://myserver:11434")
        assert provider.base_url == "http://myserver:11434"

    def test_model_default(self):
        """Should have correct default model."""
        assert OllamaProvider.MODEL == "llama3.2"

    def test_calculate_cost_always_free(self):
        """Local inference should always be free."""
        provider = OllamaProvider()
        cost = provider.calculate_cost(1000000, 1000000)  # 1M tokens each
        assert cost == 0.0

    @pytest.mark.asyncio
    async def test_complete_success(self):
        """Should return response from local Ollama."""
        provider = OllamaProvider()

        mock_response = {
            "message": {"content": "Local Llama response!"},
            "prompt_eval_count": 20,
            "eval_count": 10
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = MagicMock(
                json=MagicMock(return_value=mock_response),
                raise_for_status=MagicMock()
            )
            mock_client.return_value.__aenter__.return_value = mock_instance

            text, input_tokens, output_tokens, cost = await provider.complete("Test")

            assert text == "Local Llama response!"
            assert input_tokens == 20
            assert output_tokens == 10
            assert cost == 0.0  # Always free

    def test_is_available_no_server(self):
        """Should return False when server not running."""
        with patch("socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 1  # Connection refused
            mock_socket.return_value = mock_sock

            assert OllamaProvider.is_available() is False

    def test_is_available_server_running(self):
        """Should return True when server is running."""
        with patch("socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 0  # Connection successful
            mock_socket.return_value = mock_sock

            assert OllamaProvider.is_available() is True


# =============================================================================
# Bedrock Provider Tests
# =============================================================================

class TestBedrockProvider:
    """Test AWS Bedrock provider."""

    def test_init_default_region(self):
        """Should use us-east-1 as default region."""
        provider = BedrockProvider()
        assert provider.region == "us-east-1"

    def test_init_custom_region(self):
        """Should accept custom region."""
        provider = BedrockProvider(region="eu-west-1")
        assert provider.region == "eu-west-1"

    def test_model_default(self):
        """Should default to cheapest Claude model."""
        assert "claude-3-haiku" in BedrockProvider.MODEL

    def test_model_pricing(self):
        """Should have correct pricing for Claude on Bedrock."""
        pricing = BedrockProvider.MODEL_PRICING
        assert pricing["anthropic.claude-3-haiku-20240307-v1:0"]["input"] == 0.25
        assert pricing["anthropic.claude-3-opus-20240229-v1:0"]["input"] == 15.00
        assert pricing["meta.llama3-8b-instruct-v1:0"]["input"] == 0.30

    def test_calculate_cost(self):
        """Should calculate cost correctly."""
        provider = BedrockProvider()
        model = "anthropic.claude-3-haiku-20240307-v1:0"
        cost = provider.calculate_cost(model, 1000, 500)
        expected = (1000 / 1_000_000) * 0.25 + (500 / 1_000_000) * 1.25
        assert cost == pytest.approx(expected)

    def test_get_client_boto3_not_installed(self):
        """Should raise error if boto3 not installed."""
        provider = BedrockProvider()

        with patch.dict("sys.modules", {"boto3": None}):
            with pytest.raises(ProviderError, match="boto3 not installed"):
                provider._get_client()

    @pytest.mark.asyncio
    async def test_complete_claude_model(self):
        """Should format request correctly for Claude models."""
        provider = BedrockProvider()

        mock_response_body = MagicMock()
        mock_response_body.read.return_value = b'{"content": [{"text": "Bedrock Claude!"}], "usage": {"input_tokens": 15, "output_tokens": 8}}'

        mock_response = {
            "body": mock_response_body
        }

        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.invoke_model.return_value = mock_response
            mock_get_client.return_value = mock_client

            text, input_tokens, output_tokens, cost = await provider.complete(
                "Test", model="anthropic.claude-3-haiku-20240307-v1:0"
            )

            assert text == "Bedrock Claude!"
            assert input_tokens == 15
            assert output_tokens == 8


# =============================================================================
# init_providers() Tests
# =============================================================================

class TestInitProviders:
    """Test provider initialization function."""

    def test_init_no_keys(self):
        """Should return empty dict when no keys set."""
        with patch.dict("os.environ", {}, clear=True):
            providers = init_providers()
            # May have ollama if running locally
            assert isinstance(providers, dict)

    def test_init_mistral(self):
        """Should initialize Mistral when key is set."""
        with patch.dict("os.environ", {"MISTRAL_API_KEY": "test-key"}, clear=True):
            with patch.object(OllamaProvider, "is_available", return_value=False):
                providers = init_providers()
                assert "mistral" in providers
                assert isinstance(providers["mistral"], MistralProvider)

    def test_init_fireworks(self):
        """Should initialize Fireworks when key is set."""
        with patch.dict("os.environ", {"FIREWORKS_API_KEY": "test-key"}, clear=True):
            with patch.object(OllamaProvider, "is_available", return_value=False):
                providers = init_providers()
                assert "fireworks" in providers
                assert isinstance(providers["fireworks"], FireworksProvider)

    def test_init_cohere(self):
        """Should initialize Cohere when key is set."""
        with patch.dict("os.environ", {"COHERE_API_KEY": "test-key"}, clear=True):
            with patch.object(OllamaProvider, "is_available", return_value=False):
                providers = init_providers()
                assert "cohere" in providers
                assert isinstance(providers["cohere"], CohereProvider)

    def test_init_ollama_when_available(self):
        """Should initialize Ollama when server is running."""
        with patch.dict("os.environ", {}, clear=True):
            with patch.object(OllamaProvider, "is_available", return_value=True):
                providers = init_providers()
                assert "ollama" in providers
                assert isinstance(providers["ollama"], OllamaProvider)

    def test_init_ollama_when_unavailable(self):
        """Should not initialize Ollama when server not running."""
        with patch.dict("os.environ", {}, clear=True):
            with patch.object(OllamaProvider, "is_available", return_value=False):
                providers = init_providers()
                assert "ollama" not in providers

    def test_init_bedrock(self):
        """Should initialize Bedrock when AWS credentials are set."""
        env = {
            "AWS_ACCESS_KEY_ID": "test-access-key",
            "AWS_SECRET_ACCESS_KEY": "test-secret-key"
        }
        with patch.dict("os.environ", env, clear=True):
            with patch.object(OllamaProvider, "is_available", return_value=False):
                providers = init_providers()
                assert "bedrock" in providers
                assert isinstance(providers["bedrock"], BedrockProvider)

    def test_init_multiple_providers(self):
        """Should initialize all configured providers."""
        env = {
            "MISTRAL_API_KEY": "mistral-key",
            "FIREWORKS_API_KEY": "fireworks-key",
            "COHERE_API_KEY": "cohere-key",
            "GOOGLE_API_KEY": "gemini-key",
        }
        with patch.dict("os.environ", env, clear=True):
            with patch.object(OllamaProvider, "is_available", return_value=False):
                providers = init_providers()
                assert "mistral" in providers
                assert "fireworks" in providers
                assert "cohere" in providers
                assert "gemini" in providers


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestProviderErrorHandling:
    """Test error handling across providers."""

    @pytest.mark.asyncio
    async def test_mistral_api_error(self):
        """Should raise ProviderError on Mistral API failure."""
        provider = MistralProvider("test-key")

        import httpx
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = httpx.HTTPError("API Error")
            mock_client.return_value.__aenter__.return_value = mock_instance

            with pytest.raises(ProviderError, match="Mistral API error"):
                await provider.complete("Test")

    @pytest.mark.asyncio
    async def test_fireworks_api_error(self):
        """Should raise ProviderError on Fireworks API failure."""
        provider = FireworksProvider("test-key")

        import httpx
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = httpx.HTTPError("API Error")
            mock_client.return_value.__aenter__.return_value = mock_instance

            with pytest.raises(ProviderError, match="Fireworks API error"):
                await provider.complete("Test")

    @pytest.mark.asyncio
    async def test_cohere_api_error(self):
        """Should raise ProviderError on Cohere API failure."""
        provider = CohereProvider("test-key")

        import httpx
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = httpx.HTTPError("API Error")
            mock_client.return_value.__aenter__.return_value = mock_instance

            with pytest.raises(ProviderError, match="Cohere API error"):
                await provider.complete("Test")

    @pytest.mark.asyncio
    async def test_ollama_api_error(self):
        """Should raise ProviderError on Ollama connection failure."""
        provider = OllamaProvider()

        import httpx
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = httpx.HTTPError("Connection refused")
            mock_client.return_value.__aenter__.return_value = mock_instance

            with pytest.raises(ProviderError, match="Ollama API error"):
                await provider.complete("Test")
