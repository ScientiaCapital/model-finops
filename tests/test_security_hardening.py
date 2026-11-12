"""Security hardening: authentication, admin gate, CORS, error bodies, proxies, version."""

import importlib
import logging
from datetime import UTC, datetime, timedelta
from importlib import metadata
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app, routing_service

JWT_SECRET = "test-jwt-secret-for-testing-only"
ADMIN_KEY = "admin-key-for-tests-only-0123456789"


def make_token(sub="user-a", exp_delta=timedelta(hours=1), include_exp=True, include_sub=True):
    payload = {"aud": "authenticated", "iat": datetime.now(UTC)}
    if include_sub:
        payload["sub"] = sub
    if include_exp:
        payload["exp"] = datetime.now(UTC) + exp_delta
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def jwt_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", JWT_SECRET)
    monkeypatch.delenv("ALLOW_ANONYMOUS", raising=False)
    monkeypatch.delenv("ADMIN_API_KEY", raising=False)


@pytest.fixture
def http():
    return TestClient(app, raise_server_exceptions=False)


class FakeProvider:
    MODEL = "fake-model"

    async def complete(self, prompt, max_tokens=1000):
        return "fake answer", 3, 2, 0.0


# ----------------------------------------------------------------------------
# S2: invalid credentials fail closed, anonymous /complete is opt-in
# ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path", ["/stats", "/recommendation?prompt=hi", "/cache/stats", "/routing/decision?prompt=hi"]
)
@pytest.mark.parametrize("header", ["Bearer not-a-jwt", "Basic abc", "Bearer "])
def test_invalid_authorization_header_is_401(http, path, header):
    response = http.get(path, headers={"Authorization": header})
    assert response.status_code == 401, response.text


def test_expired_token_is_401(http):
    token = make_token(exp_delta=timedelta(hours=-1))
    assert http.get("/stats", headers=bearer(token)).status_code == 401


def test_token_signed_with_wrong_secret_is_401(http):
    token = jwt.encode(
        {"sub": "x", "aud": "authenticated", "exp": datetime.now(UTC) + timedelta(hours=1)},
        "some-other-secret-value-of-enough-length",
        algorithm="HS256",
    )
    assert http.get("/stats", headers=bearer(token)).status_code == 401


def test_verify_requires_exp_and_sub():
    from fastapi import HTTPException

    from app.auth import verify_jwt_token

    for kwargs in ({"include_exp": False}, {"include_sub": False}):
        with pytest.raises(HTTPException) as exc:
            verify_jwt_token(make_token(**kwargs))
        assert exc.value.status_code == 401
    assert verify_jwt_token(make_token())["sub"] == "user-a"


def test_token_with_no_jwt_secret_configured_is_503_not_anonymous(http, monkeypatch):
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    response = http.get("/stats", headers=bearer(make_token()))
    assert response.status_code == 503
    assert "secret" not in response.text.lower().replace("authentication configuration", "")


def test_complete_without_token_is_401_by_default(http):
    response = http.post("/complete", json={"prompt": "hi"})
    assert response.status_code == 401


def test_complete_with_invalid_token_is_401_even_when_anonymous_allowed(http, monkeypatch):
    monkeypatch.setenv("ALLOW_ANONYMOUS", "true")
    response = http.post("/complete", json={"prompt": "hi"}, headers={"Authorization": "Bearer x"})
    assert response.status_code == 401


def test_complete_anonymous_allowed_when_env_true(http, monkeypatch):
    monkeypatch.setenv("ALLOW_ANONYMOUS", "true")
    with patch.object(
        routing_service, "route_and_complete", new_callable=AsyncMock
    ) as route_and_complete:
        route_and_complete.return_value = _fake_result()
        response = http.post("/complete", json={"prompt": "hi"})
    assert response.status_code == 200, response.text
    assert route_and_complete.await_args.kwargs["user_id"] is None


@pytest.mark.parametrize("value", ["", "false", "0", "no", "yes please", "TRUEISH"])
def test_allow_anonymous_only_true_values_count(http, monkeypatch, value):
    monkeypatch.setenv("ALLOW_ANONYMOUS", value)
    assert http.post("/complete", json={"prompt": "hi"}).status_code == 401


def test_complete_with_valid_token_passes_user_id_to_routing(http):
    with patch.object(
        routing_service, "route_and_complete", new_callable=AsyncMock
    ) as route_and_complete:
        route_and_complete.return_value = _fake_result()
        response = http.post("/complete", json={"prompt": "hi"}, headers=bearer(make_token()))
    assert response.status_code == 200, response.text
    assert route_and_complete.await_args.kwargs["user_id"] == "user-a"


def test_health_stays_public(http):
    assert http.get("/health").status_code == 200


def _fake_result():
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


# ----------------------------------------------------------------------------
# S1: admin routes need ADMIN_API_KEY, fail closed
# ----------------------------------------------------------------------------

ADMIN_ROUTES = [
    ("get", "/admin/feedback/summary"),
    ("get", "/admin/learning/status"),
    ("post", "/admin/learning/retrain?dry_run=false"),
    ("get", "/admin/performance/trends?pattern=code"),
]


@pytest.mark.parametrize(("method", "path"), ADMIN_ROUTES)
def test_admin_routes_closed_when_key_unset(http, method, path):
    with patch("app.main.feedback_trainer.retrain") as retrain:
        response = getattr(http, method)(path)
        with_user = getattr(http, method)(path, headers=bearer(make_token()))
    assert response.status_code == 503
    assert with_user.status_code == 503
    retrain.assert_not_called()


@pytest.mark.parametrize(("method", "path"), ADMIN_ROUTES)
def test_admin_routes_reject_missing_or_wrong_key(http, monkeypatch, method, path):
    monkeypatch.setenv("ADMIN_API_KEY", ADMIN_KEY)
    with patch("app.main.feedback_trainer.retrain") as retrain:
        missing = getattr(http, method)(path)
        wrong = getattr(http, method)(path, headers={"X-Admin-Key": "nope"})
        user_token = getattr(http, method)(path, headers=bearer(make_token()))
    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert user_token.status_code == 401
    retrain.assert_not_called()


def test_admin_retrain_runs_with_correct_key(http, monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", ADMIN_KEY)
    result = {
        "run_id": "run-1",
        "timestamp": "2026-01-01T00:00:00",
        "patterns_updated": 0,
        "total_changes": 0,
        "changes": [],
        "dry_run": False,
    }
    with (
        patch("app.main.scheduler", None),
        patch("app.main.feedback_trainer.retrain", return_value=result) as retrain,
    ):
        response = http.post(
            "/admin/learning/retrain?dry_run=false", headers={"X-Admin-Key": ADMIN_KEY}
        )
    assert response.status_code == 200, response.text
    retrain.assert_called_once_with(dry_run=False)


def test_admin_key_compared_in_constant_time(monkeypatch):
    import app.auth as auth

    monkeypatch.setenv("ADMIN_API_KEY", ADMIN_KEY)
    with (
        patch.object(auth.hmac, "compare_digest", wraps=auth.hmac.compare_digest) as spy,
        pytest.raises(HTTPException),
    ):
        auth.require_admin(x_admin_key="wrong")
    assert spy.called


def test_production_feedback_requires_valid_user_token(http):
    body = {"request_id": "r1", "quality_score": 0.9, "is_correct": True, "is_helpful": True}
    assert http.post("/production/feedback", json=body).status_code in (401, 403)
    assert (
        http.post(
            "/production/feedback", json=body, headers={"Authorization": "Bearer x"}
        ).status_code
        == 401
    )


# ----------------------------------------------------------------------------
# S4: CORS
# ----------------------------------------------------------------------------


def _cors_settings(monkeypatch, value):
    from app import main

    if value is None:
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
    else:
        monkeypatch.setenv("CORS_ORIGINS", value)
    return main.resolve_cors_settings()


def test_cors_default_allows_no_origin(monkeypatch):
    origins, credentials = _cors_settings(monkeypatch, None)
    assert origins == []
    assert credentials is False


def test_cors_uses_configured_list_with_credentials(monkeypatch):
    origins, credentials = _cors_settings(monkeypatch, "https://a.example, https://b.example")
    assert origins == ["https://a.example", "https://b.example"]
    assert credentials is True


def test_cors_wildcard_never_combined_with_credentials(monkeypatch):
    origins, credentials = _cors_settings(monkeypatch, "*")
    assert origins == ["*"]
    assert credentials is False


def test_cors_preflight_from_unlisted_origin_gets_no_allow_header(http):
    response = http.options(
        "/complete",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in response.headers


# ----------------------------------------------------------------------------
# S7: generic error bodies
# ----------------------------------------------------------------------------


def test_complete_unexpected_error_is_generic(http, caplog, monkeypatch):
    monkeypatch.setenv("ALLOW_ANONYMOUS", "true")
    secret = "db-password-hunter2-in-message"
    with (
        patch.object(
            routing_service,
            "route_and_complete",
            new_callable=AsyncMock,
            side_effect=RuntimeError(secret),
        ),
        caplog.at_level(logging.ERROR),
    ):
        response = http.post("/complete", json={"prompt": "hi"})
    assert response.status_code == 500
    assert secret not in response.text
    assert response.json()["detail"] == "internal error"
    assert secret in caplog.text


def test_global_handler_returns_request_id_and_hides_message(http, caplog):
    secret = "internal-path-/srv/app/secret.py"

    @app.get("/__boom_test")
    async def boom():
        raise RuntimeError(secret)

    route = app.router.routes[-1]
    try:
        with caplog.at_level(logging.ERROR):
            response = http.get("/__boom_test")
    finally:
        app.router.routes.remove(route)
    assert response.status_code == 500
    body = response.json()
    assert body["detail"] == "internal error"
    assert body["request_id"]
    assert secret not in response.text
    assert secret in caplog.text


# ----------------------------------------------------------------------------
# S8: X-Forwarded-For only behind a configured proxy
# ----------------------------------------------------------------------------


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


def _middleware():
    from app.middleware.api_key_auth import APIKeyMiddleware

    return APIKeyMiddleware(app=lambda *a: None)


def test_forwarded_for_ignored_by_default(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXY_COUNT", raising=False)
    request = _request({"X-Forwarded-For": "1.2.3.4", "X-Real-IP": "5.6.7.8"})
    assert _middleware()._get_client_ip(request) == "10.0.0.9"


def test_forwarded_for_honored_with_one_trusted_proxy(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_COUNT", "1")
    request = _request({"X-Forwarded-For": "6.6.6.6, 1.2.3.4"})
    # One trusted proxy appended the last entry; the client is the entry it saw.
    assert _middleware()._get_client_ip(request) == "1.2.3.4"


def test_forwarded_for_counts_from_the_right_with_two_proxies(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_COUNT", "2")
    request = _request({"X-Forwarded-For": "6.6.6.6, 1.2.3.4, 10.1.1.1"})
    assert _middleware()._get_client_ip(request) == "1.2.3.4"


@pytest.mark.parametrize("value", ["", "abc", "-1", "0"])
def test_bad_trusted_proxy_count_means_off(monkeypatch, value):
    monkeypatch.setenv("TRUSTED_PROXY_COUNT", value)
    request = _request({"X-Forwarded-For": "1.2.3.4"})
    assert _middleware()._get_client_ip(request) == "10.0.0.9"


# ----------------------------------------------------------------------------
# V1: one version, read from package metadata
# ----------------------------------------------------------------------------


def _pyproject_version():
    import tomllib
    from pathlib import Path

    return tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"]


def test_version_single_sourced(http):
    expected = _pyproject_version()
    assert http.get("/health").json()["version"] == expected
    assert app.version == expected
    assert http.get("/openapi.json").json()["info"]["version"] == expected


def test_version_prefers_installed_package_metadata():
    import app.version as version_module

    try:
        with patch.object(metadata, "version", return_value="9.9.9"):
            assert importlib.reload(version_module).__version__ == "9.9.9"
    finally:
        importlib.reload(version_module)


def test_version_reads_pyproject_when_not_installed():
    import app.version as version_module

    try:
        with patch.object(metadata, "version", side_effect=metadata.PackageNotFoundError):
            assert importlib.reload(version_module).__version__ == _pyproject_version()
    finally:
        importlib.reload(version_module)
