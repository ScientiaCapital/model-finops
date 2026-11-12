"""With no provider configured, /complete and /routing/decision answer 503, not 500.

Also covers the routing candidate set: a decision may only name a configured provider.
"""

import os
from unittest.mock import AsyncMock, patch

import pytest

from app.main import routing_service
from app.providers import PROVIDER_REGISTRY, NoProvidersConfiguredError, no_provider_message

ALL_PROVIDER_ENV_VARS = sorted({var for spec in PROVIDER_REGISTRY for var in spec.env_vars})

# These tests exercise caching and routing, not authentication, so anonymous /complete is on.
pytestmark = pytest.mark.usefixtures("allow_anonymous")


class FakeProvider:
    """Stands in for a configured provider; never touches the network."""

    MODEL = "fake-model"

    async def complete(self, prompt: str, max_tokens: int = 1000) -> tuple[str, int, int, float]:
        return "fake answer", 3, 2, 0.0


@pytest.fixture
def no_providers():
    with (
        patch.object(routing_service, "providers", {}),
        patch.object(routing_service.cost_tracker, "check_cache", AsyncMock(return_value=None)),
    ):
        yield


@pytest.fixture
def secret_env():
    """A key-shaped value in the environment that must never reach a response body."""
    with patch.dict(os.environ, {"SUPABASE_SERVICE_KEY": "sk-should-never-leak-123"}):
        yield "sk-should-never-leak-123"


def _assert_clean_503(response, secret: str) -> None:
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail.startswith("no model provider is configured; set one of ")
    for var in ALL_PROVIDER_ENV_VARS:
        assert var in detail
    assert secret not in response.text
    assert os.getcwd() not in response.text
    assert "Traceback" not in response.text
    assert "Internal error" not in response.text


def test_message_is_derived_from_registry():
    message = no_provider_message()
    for spec in PROVIDER_REGISTRY:
        for var in spec.env_vars:
            assert var in message
    assert str(NoProvidersConfiguredError()) == message


def test_complete_without_providers_returns_503(client, no_providers, secret_env):
    response = client.post("/complete", json={"prompt": "What is Python?"})
    _assert_clean_503(response, secret_env)


def test_complete_with_override_and_no_providers_returns_503(client, no_providers, secret_env):
    response = client.post("/complete", json={"prompt": "What is Python?", "provider": "claude"})
    _assert_clean_503(response, secret_env)


def test_routing_decision_without_providers_returns_503(client, no_providers, secret_env):
    response = client.get("/routing/decision", params={"prompt": "What is Python?"})
    _assert_clean_503(response, secret_env)


@pytest.mark.parametrize("prompt", ["Hello", "Explain how HTTP works", "word " * 400])
def test_recommendation_only_names_configured_providers(prompt):
    with patch.object(routing_service, "providers", {"deepseek": FakeProvider()}):
        recommendation = routing_service.get_recommendation(prompt=prompt)
    assert recommendation["provider"] == "deepseek"


def test_routing_decision_endpoint_picks_configured_provider(client):
    with patch.object(routing_service, "providers", {"deepseek": FakeProvider()}):
        response = client.get("/routing/decision", params={"prompt": "Hello"})
    assert response.status_code == 200, response.text
    assert response.json()["decision"]["provider"] == "deepseek"


def test_unlisted_provider_gets_its_own_model_name():
    """A configured provider the strategies have no model table for still gets a real model."""
    with patch.object(routing_service, "providers", {"groq": FakeProvider()}):
        recommendation = routing_service.get_recommendation(prompt="Hello")
    assert recommendation["provider"] == "groq"
    assert recommendation["model"] == "fake-model"
