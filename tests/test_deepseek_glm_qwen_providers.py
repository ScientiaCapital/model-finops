"""
Tests for DeepSeek, GLM (Zhipu), and Qwen (DashScope) providers.

All three are OpenAI-compatible /chat/completions providers, mirroring the
CerebrasProvider shape. Uses mocked HTTP responses for unit testing — no live
API calls (no real keys exist yet for these vendors).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.providers import (
    DeepSeekProvider,
    GLMProvider,
    QwenProvider,
    OllamaProvider,
    ProviderError,
    init_providers,
)


# =============================================================================
# DeepSeek Provider Tests
# =============================================================================

class TestDeepSeekProvider:
    """Test DeepSeek provider."""

    def test_init(self):
        """Should initialize with API key."""
        provider = DeepSeekProvider("test-api-key")
        assert provider.api_key == "test-api-key"
        assert provider.MODEL == "deepseek-chat"
        assert provider.BASE_URL == "https://api.deepseek.com/v1"

    def test_model_pricing(self):
        """Should have pricing for chat and reasoner models."""
        pricing = DeepSeekProvider.MODEL_PRICING
        assert "deepseek-chat" in pricing
        assert "deepseek-reasoner" in pricing
        assert pricing["deepseek-chat"]["input"] > 0
        assert pricing["deepseek-chat"]["output"] > 0

    def test_calculate_cost(self):
        """Should calculate cost correctly."""
        provider = DeepSeekProvider("test-key")
        pricing = DeepSeekProvider.MODEL_PRICING["deepseek-chat"]
        cost = provider.calculate_cost("deepseek-chat", 1000, 500)
        expected = (1000 / 1_000_000) * pricing["input"] + (500 / 1_000_000) * pricing["output"]
        assert cost == pytest.approx(expected)

    @pytest.mark.asyncio
    async def test_complete_success(self):
        """Should return response on successful completion."""
        provider = DeepSeekProvider("test-key")

        mock_response = {
            "choices": [{"message": {"content": "Hello from DeepSeek!"}}],
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

            assert text == "Hello from DeepSeek!"
            assert input_tokens == 10
            assert output_tokens == 5
            assert cost > 0


# =============================================================================
# GLM (Zhipu) Provider Tests
# =============================================================================

class TestGLMProvider:
    """Test GLM (Zhipu BigModel) provider."""

    def test_init(self):
        """Should initialize with API key."""
        provider = GLMProvider("test-api-key")
        assert provider.api_key == "test-api-key"
        assert provider.MODEL == "glm-4.7"
        assert provider.BASE_URL == "https://open.bigmodel.cn/api/paas/v4"

    def test_model_pricing(self):
        """Should have pricing for the default model."""
        pricing = GLMProvider.MODEL_PRICING
        assert "glm-4.7" in pricing
        assert pricing["glm-4.7"]["input"] > 0
        assert pricing["glm-4.7"]["output"] > 0

    def test_calculate_cost(self):
        """Should calculate cost correctly."""
        provider = GLMProvider("test-key")
        pricing = GLMProvider.MODEL_PRICING["glm-4.7"]
        cost = provider.calculate_cost("glm-4.7", 1000, 500)
        expected = (1000 / 1_000_000) * pricing["input"] + (500 / 1_000_000) * pricing["output"]
        assert cost == pytest.approx(expected)

    @pytest.mark.asyncio
    async def test_complete_success(self):
        """Should return response on successful completion."""
        provider = GLMProvider("test-key")

        mock_response = {
            "choices": [{"message": {"content": "Hello from GLM!"}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 7}
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = MagicMock(
                json=MagicMock(return_value=mock_response),
                raise_for_status=MagicMock()
            )
            mock_client.return_value.__aenter__.return_value = mock_instance

            text, input_tokens, output_tokens, cost = await provider.complete("Hello")

            assert text == "Hello from GLM!"
            assert input_tokens == 12
            assert output_tokens == 7
            assert cost > 0


# =============================================================================
# Qwen (DashScope) Provider Tests
# =============================================================================

class TestQwenProvider:
    """Test Qwen (Alibaba DashScope) provider."""

    def test_init(self):
        """Should initialize with API key."""
        provider = QwenProvider("test-api-key")
        assert provider.api_key == "test-api-key"
        assert provider.MODEL == "qwen-plus"
        assert provider.BASE_URL == "https://dashscope.aliyuncs.com/compatible-mode/v1"

    def test_model_pricing(self):
        """Should have pricing for the default model."""
        pricing = QwenProvider.MODEL_PRICING
        assert "qwen-plus" in pricing
        assert pricing["qwen-plus"]["input"] > 0
        assert pricing["qwen-plus"]["output"] > 0

    def test_calculate_cost(self):
        """Should calculate cost correctly."""
        provider = QwenProvider("test-key")
        pricing = QwenProvider.MODEL_PRICING["qwen-plus"]
        cost = provider.calculate_cost("qwen-plus", 1000, 500)
        expected = (1000 / 1_000_000) * pricing["input"] + (500 / 1_000_000) * pricing["output"]
        assert cost == pytest.approx(expected)

    @pytest.mark.asyncio
    async def test_complete_success(self):
        """Should return response on successful completion."""
        provider = QwenProvider("test-key")

        mock_response = {
            "choices": [{"message": {"content": "Hello from Qwen!"}}],
            "usage": {"prompt_tokens": 14, "completion_tokens": 9}
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = MagicMock(
                json=MagicMock(return_value=mock_response),
                raise_for_status=MagicMock()
            )
            mock_client.return_value.__aenter__.return_value = mock_instance

            text, input_tokens, output_tokens, cost = await provider.complete("Hello")

            assert text == "Hello from Qwen!"
            assert input_tokens == 14
            assert output_tokens == 9
            assert cost > 0


# =============================================================================
# init_providers() Tests
# =============================================================================

class TestInitProviders:
    """Test provider initialization for the new providers."""

    def test_init_deepseek(self):
        """Should initialize DeepSeek when key is set."""
        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key"}, clear=True):
            with patch.object(OllamaProvider, "is_available", return_value=False):
                providers = init_providers()
                assert "deepseek" in providers
                assert isinstance(providers["deepseek"], DeepSeekProvider)

    def test_init_glm(self):
        """Should initialize GLM when key is set."""
        with patch.dict("os.environ", {"GLM_API_KEY": "test-key"}, clear=True):
            with patch.object(OllamaProvider, "is_available", return_value=False):
                providers = init_providers()
                assert "glm" in providers
                assert isinstance(providers["glm"], GLMProvider)

    def test_init_qwen(self):
        """Should initialize Qwen when DashScope key is set."""
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "test-key"}, clear=True):
            with patch.object(OllamaProvider, "is_available", return_value=False):
                providers = init_providers()
                assert "qwen" in providers
                assert isinstance(providers["qwen"], QwenProvider)

    def test_init_all_three(self):
        """Should initialize all three when all keys are set."""
        env = {
            "DEEPSEEK_API_KEY": "ds-key",
            "GLM_API_KEY": "glm-key",
            "DASHSCOPE_API_KEY": "qwen-key",
        }
        with patch.dict("os.environ", env, clear=True):
            with patch.object(OllamaProvider, "is_available", return_value=False):
                providers = init_providers()
                assert "deepseek" in providers
                assert "glm" in providers
                assert "qwen" in providers

    def test_init_none_when_no_keys(self):
        """Should not initialize new providers when their keys are absent."""
        with patch.dict("os.environ", {}, clear=True):
            with patch.object(OllamaProvider, "is_available", return_value=False):
                providers = init_providers()
                assert "deepseek" not in providers
                assert "glm" not in providers
                assert "qwen" not in providers


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestProviderErrorHandling:
    """Test error handling across the new providers."""

    @pytest.mark.asyncio
    async def test_deepseek_api_error(self):
        """Should raise ProviderError on DeepSeek API failure."""
        provider = DeepSeekProvider("test-key")

        import httpx
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = httpx.HTTPError("API Error")
            mock_client.return_value.__aenter__.return_value = mock_instance

            with pytest.raises(ProviderError, match="DeepSeek API error"):
                await provider.complete("Test")

    @pytest.mark.asyncio
    async def test_glm_api_error(self):
        """Should raise ProviderError on GLM API failure."""
        provider = GLMProvider("test-key")

        import httpx
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = httpx.HTTPError("API Error")
            mock_client.return_value.__aenter__.return_value = mock_instance

            with pytest.raises(ProviderError, match="GLM API error"):
                await provider.complete("Test")

    @pytest.mark.asyncio
    async def test_qwen_api_error(self):
        """Should raise ProviderError on Qwen API failure."""
        provider = QwenProvider("test-key")

        import httpx
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = httpx.HTTPError("API Error")
            mock_client.return_value.__aenter__.return_value = mock_instance

            with pytest.raises(ProviderError, match="Qwen API error"):
                await provider.complete("Test")
