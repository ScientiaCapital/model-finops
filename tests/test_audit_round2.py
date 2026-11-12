"""Second-round audit fixes: /complete identity, operator read routes, small hardening items."""

import os
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient

from app.main import app, routing_service

JWT_SECRET = "test-jwt-secret-for-testing-only"
LEAK = "[Errno 61] Connection refused"


def token(sub="user-a"):
    return jwt.encode(
        {"sub": sub, "aud": "authenticated", "exp": datetime.now(UTC) + timedelta(hours=1)},
        JWT_SECRET,
        algorithm="HS256",
    )


def bearer(sub="user-a"):
    return {"Authorization": f"Bearer {token(sub)}"}


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", JWT_SECRET)
    monkeypatch.delenv("ALLOW_ANONYMOUS", raising=False)
    monkeypatch.delenv("MAX_PROMPT_CHARS", raising=False)


@pytest.fixture
def http():
    return TestClient(app, raise_server_exceptions=False)


def fake_result():
    return {
        "request_id": "r1",
        "response": "ok",
        "provider": "fake",
        "model": "m",
        "strategy_used": "complexity",
        "confidence": "high",
        "complexity_metadata": {},
        "routing_metadata": {},
        "tokens_in": 1,
        "tokens_out": 1,
        "cost": 0.0,
        "total_cost_today": 0.0,
        "cache_hit": False,
    }


# ---- M2: /complete uses the token subject, not the body user_id -----------------


def test_complete_records_the_token_user_not_the_body_user_id(http):
    tracker = MagicMock()
    tracker.get_active_experiments.return_value = [{"id": 7}]
    tracker.assign_user.return_value = "complexity"
    with (
        patch("app.main.experiment_tracker", tracker),
        patch.object(routing_service, "route_and_complete", new_callable=AsyncMock) as route,
    ):
        route.return_value = fake_result()
        response = http.post(
            "/complete", json={"prompt": "hi", "user_id": "victim"}, headers=bearer("user-a")
        )
    assert response.status_code == 200, response.text
    assert tracker.assign_user.call_args.args == (7, "user-a")
    assert tracker.record_result.call_args.kwargs["user_id"] == "user-a"
    assert route.await_args.kwargs["user_id"] == "user-a"


def test_anonymous_complete_ignores_the_body_user_id(http, monkeypatch):
    monkeypatch.setenv("ALLOW_ANONYMOUS", "true")
    tracker = MagicMock()
    tracker.get_active_experiments.return_value = [{"id": 7}]
    with (
        patch("app.main.experiment_tracker", tracker),
        patch.object(routing_service, "route_and_complete", new_callable=AsyncMock) as route,
    ):
        route.return_value = fake_result()
        response = http.post("/complete", json={"prompt": "hi", "user_id": "victim"})
    assert response.status_code == 200, response.text
    tracker.assign_user.assert_not_called()
    tracker.record_result.assert_not_called()


# ---- M3: operator-wide read routes need a token and do not echo errors ----------

BOOM = OSError(LEAK)


def _analytics_db():
    db = MagicMock()
    db.get_cache_analytics = AsyncMock(side_effect=BOOM)
    return db


def _tracker(name, mock):
    return lambda: patch.object(routing_service.cost_tracker, name, mock)


def _service(name, mock):
    return lambda: patch.object(routing_service, name, mock)


ROUTES = [
    ("/stats", _tracker("get_usage_stats", AsyncMock(side_effect=BOOM))),
    ("/recommendation?prompt=hi", _service("get_recommendation", MagicMock(side_effect=BOOM))),
    ("/routing/decision?prompt=hi", _service("get_recommendation", MagicMock(side_effect=BOOM))),
    ("/routing/metrics", _service("get_routing_metrics", AsyncMock(side_effect=BOOM))),
    ("/cache/stats", _tracker("get_cache_stats", AsyncMock(side_effect=BOOM))),
    ("/quality/stats", _tracker("get_quality_stats", MagicMock(side_effect=BOOM))),
    (
        "/analytics/cache",
        lambda: patch("app.database.get_supabase_client", return_value=_analytics_db()),
    ),
    ("/analytics/costs", _tracker("get_usage_stats", AsyncMock(side_effect=BOOM))),
    (
        "/analytics/provider-usage",
        lambda: patch(
            "app.services.provider_usage.get_all_provider_usage", AsyncMock(side_effect=BOOM)
        ),
    ),
]
PATHS = [r[0] for r in ROUTES] + ["/metrics-cache/stats", "/insights"]


@pytest.mark.parametrize("path", PATHS)
def test_operator_read_routes_refuse_anonymous_callers(http, path):
    assert http.get(path).status_code == 401


@pytest.mark.parametrize("path", ["/stats", "/cache/stats", "/routing/metrics"])
def test_operator_read_routes_follow_allow_anonymous(http, monkeypatch, path):
    monkeypatch.setenv("ALLOW_ANONYMOUS", "true")
    with (
        patch.object(routing_service.cost_tracker, "get_usage_stats", AsyncMock(side_effect=BOOM)),
        patch.object(routing_service.cost_tracker, "get_cache_stats", AsyncMock(side_effect=BOOM)),
        patch.object(routing_service, "get_routing_metrics", AsyncMock(side_effect=BOOM)),
        patch("app.main.metrics_cache", MagicMock(get=MagicMock(return_value=None))),
    ):
        assert http.get(path).status_code == 500  # past the auth gate, then the backend failed


@pytest.mark.parametrize(("path", "make_patch"), ROUTES, ids=[r[0] for r in ROUTES])
def test_operator_read_routes_return_a_generic_error_body(http, path, make_patch):
    with (
        make_patch(),
        patch("app.main.metrics_cache", MagicMock(get=MagicMock(return_value=None))),
    ):
        response = http.get(path, headers=bearer())
    assert response.status_code == 500
    assert "Errno" not in response.text and "refused" not in response.text.lower()
    assert response.json()["detail"] == "internal error"


# ---- L1: telemetry token compare ------------------------------------------------


def test_telemetry_non_ascii_token_is_401_not_500(monkeypatch):
    from fastapi import FastAPI

    from app.routers import telemetry

    monkeypatch.setenv("FINOPS_INGEST_TOKEN", "expected-token")
    mini = FastAPI()
    mini.include_router(telemetry.router)
    client = TestClient(mini, raise_server_exceptions=False)
    payload = {"provider": "p", "model": "m", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0}
    response = client.post(
        "/api/telemetry/ingest",
        json=payload,
        headers={"Authorization": "Bearer café".encode()},
    )
    assert response.status_code == 401


# ---- L2: ENCRYPTION_KEY length and wrong-key errors -----------------------------


def test_short_encryption_key_is_refused_with_a_clear_error():
    from app.services.encryption_service import EncryptionConfigError, EncryptionService

    with pytest.raises(EncryptionConfigError, match="at least 32"):
        EncryptionService(key="too-short").encrypt("x")
    with (
        patch.dict(os.environ, {"ENCRYPTION_KEY": "short"}),
        pytest.raises(EncryptionConfigError, match="at least 32"),
    ):
        EncryptionService().encrypt("x")


def test_wrong_key_decrypt_raises_a_clear_error_not_invalid_tag():
    from app.services.encryption_service import EncryptionService

    blob = EncryptionService(key="a" * 40).encrypt("sk-secret")
    with pytest.raises(ValueError, match="could not be decrypted") as exc:
        EncryptionService(key="b" * 40).decrypt(blob)
    assert type(exc.value).__name__ == "ValueError"
    assert "sk-secret" not in str(exc.value)


# ---- L3: X-Forwarded-For hop is validated ---------------------------------------


def _request(headers, client_host="10.0.0.9"):
    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": (client_host, 1234),
    }
    return Request(scope)


@pytest.mark.parametrize("hop", ["not-an-ip", "1.2.3.4; DROP TABLE x", "<script>", "999.1.1.1"])
def test_invalid_forwarded_hop_falls_back_to_the_socket_address(monkeypatch, hop):
    from app.middleware.api_key_auth import APIKeyMiddleware

    monkeypatch.setenv("TRUSTED_PROXY_COUNT", "1")
    middleware = APIKeyMiddleware(app=lambda *a: None)
    assert middleware._get_client_ip(_request({"X-Forwarded-For": hop})) == "10.0.0.9"


def test_valid_forwarded_hops_are_still_used(monkeypatch):
    from app.middleware.api_key_auth import APIKeyMiddleware

    monkeypatch.setenv("TRUSTED_PROXY_COUNT", "1")
    middleware = APIKeyMiddleware(app=lambda *a: None)
    assert middleware._get_client_ip(_request({"X-Forwarded-For": "1.2.3.4"})) == "1.2.3.4"
    assert middleware._get_client_ip(_request({"X-Forwarded-For": "2001:db8::1"})) == "2001:db8::1"


# ---- L4: prompt size ------------------------------------------------------------


def test_oversized_prompt_is_refused_before_any_routing(http, monkeypatch):
    monkeypatch.setenv("MAX_PROMPT_CHARS", "50")
    with patch.object(routing_service, "route_and_complete", new_callable=AsyncMock) as route:
        route.return_value = fake_result()
        too_big = http.post("/complete", json={"prompt": "x" * 51}, headers=bearer())
        fits = http.post("/complete", json={"prompt": "x" * 50}, headers=bearer())
    assert too_big.status_code == 413
    assert route.await_count == 1
    assert fits.status_code == 200


def test_default_prompt_limit_is_100000_characters(http):
    with patch.object(routing_service, "route_and_complete", new_callable=AsyncMock) as route:
        route.return_value = fake_result()
        assert (
            http.post("/complete", json={"prompt": "x" * 100_001}, headers=bearer()).status_code
            == 413
        )
        assert (
            http.post("/complete", json={"prompt": "x" * 100_000}, headers=bearer()).status_code
            == 200
        )


# ---- L5: no JWT secret configured -> 503 ----------------------------------------


def test_token_with_no_jwt_secret_configured_is_503(http, monkeypatch):
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    response = http.get("/stats", headers={"Authorization": "Bearer abc.def.ghi"})
    assert response.status_code == 503
    assert response.json()["detail"] == "Server authentication configuration error"
