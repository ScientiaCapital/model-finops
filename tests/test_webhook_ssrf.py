"""Budget alert webhooks cannot be pointed at internal addresses (SSRF).

No real network: socket.getaddrinfo is faked and httpx uses a mock transport.
"""

import socket
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.network.ssrf import UnsafeURLError, resolve_public_https
from app.services.budget_alerting import BudgetAlertingService, BudgetConfig

JWT_SECRET = "test-jwt-secret-for-testing-only"
PUBLIC_IP = "93.184.216.34"

HOSTS = {
    "hooks.example.com": [PUBLIC_IP],
    "rebind.example.com": ["10.0.0.7"],
    "mixed.example.com": [PUBLIC_IP, "169.254.169.254"],
    "mapped.example.com": ["::ffff:169.254.169.254"],
    "local.example.com": ["127.0.0.1"],
}


def fake_getaddrinfo(host, port, *args, **kwargs):
    if host == "localhost":
        answers = ["127.0.0.1"]
    elif host in HOSTS:
        answers = HOSTS[host]
    else:
        raise socket.gaierror("unknown host")
    return [
        (socket.AF_INET6 if ":" in a else socket.AF_INET, socket.SOCK_STREAM, 6, "", (a, port))
        for a in answers
    ]


@pytest.fixture(autouse=True)
def no_dns():
    with patch("app.network.ssrf.socket.getaddrinfo", side_effect=fake_getaddrinfo) as fake:
        yield fake


BAD_URLS = [
    "https://169.254.169.254/latest/meta-data/",
    "https://[::ffff:169.254.169.254]/latest/meta-data/",
    "https://[::ffff:a9fe:a9fe]/",
    "https://127.0.0.1/hook",
    "https://[::1]/hook",
    "https://10.1.2.3/hook",
    "https://192.168.0.5/hook",
    "https://100.64.0.1/hook",
    "https://0.0.0.0/hook",
    "https://[::]/hook",
    "https://localhost/hook",
    "http://hooks.example.com/hook",
    "ftp://hooks.example.com/hook",
    "https://rebind.example.com/hook",
    "https://mixed.example.com/hook",
    "https://mapped.example.com/hook",
    "https://nonexistent.example.com/hook",
    "https://user:pw@hooks.example.com/hook",
    "https:///hook",
    "not a url",
]


@pytest.mark.parametrize("url", BAD_URLS)
def test_guard_refuses_unsafe_urls(url):
    with pytest.raises(UnsafeURLError):
        resolve_public_https(url)


def test_guard_accepts_public_https_and_returns_the_checked_address():
    target = resolve_public_https("https://hooks.example.com/services/T0/B0?x=1")
    assert target.addresses == (PUBLIC_IP,)
    assert target.port == 443
    assert target.path_query == "/services/T0/B0?x=1"


def test_guard_fails_closed_when_resolution_errors(no_dns):
    no_dns.side_effect = OSError("resolver down")
    with pytest.raises(UnsafeURLError):
        resolve_public_https("https://hooks.example.com/hook")


# ---- send time ---------------------------------------------------------------


def make_service(handler):
    service = BudgetAlertingService()
    service.http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return service


def config_with(**urls):
    return BudgetConfig(user_id="user-a", monthly_budget=100.0, alert_thresholds=[0.5], **urls)


@pytest.mark.parametrize(
    "url",
    [
        "https://169.254.169.254/latest/meta-data/",
        "https://[::ffff:169.254.169.254]/x",
        "https://127.0.0.1/x",
        "https://10.1.2.3/x",
        "https://localhost/x",
        "http://hooks.example.com/x",
        "https://rebind.example.com/x",
    ],
)
async def test_send_time_blocks_unsafe_webhook_even_if_it_was_saved(url):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200)

    service = make_service(handler)
    channels = await service._send_alert(config_with(alert_webhook_url=url), 0.5, 50.0)
    assert seen == []
    assert "webhook" not in channels


async def test_send_time_blocks_slack_and_discord_urls_too():
    seen = []
    service = make_service(lambda r: seen.append(r) or httpx.Response(200))
    await service._send_alert(
        config_with(
            slack_webhook_url="https://10.0.0.1/slack", discord_webhook_url="https://127.0.0.1/d"
        ),
        0.5,
        50.0,
    )
    assert seen == []


async def test_public_https_webhook_still_works_and_connects_to_the_checked_address():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200)

    service = make_service(handler)
    channels = await service._send_alert(
        config_with(alert_webhook_url="https://hooks.example.com/services/abc"), 0.5, 50.0
    )
    assert "webhook" in channels
    assert len(seen) == 1
    assert seen[0].url.host == PUBLIC_IP
    assert seen[0].url.path == "/services/abc"
    assert seen[0].headers["host"] == "hooks.example.com"
    assert seen[0].extensions["sni_hostname"] == "hooks.example.com"


async def test_redirect_to_a_private_address_is_not_followed():
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(302, headers={"Location": "http://169.254.169.254/latest/"})

    service = make_service(handler)
    channels = await service._send_alert(
        config_with(alert_webhook_url="https://hooks.example.com/r"), 0.5, 50.0
    )
    assert len(seen) == 1
    assert "169.254.169.254" not in seen[0]
    assert "webhook" not in channels


# ---- save time ---------------------------------------------------------------


def token(sub="user-a"):
    return jwt.encode(
        {"sub": sub, "aud": "authenticated", "exp": datetime.now(UTC) + timedelta(hours=1)},
        JWT_SECRET,
        algorithm="HS256",
    )


@pytest.fixture
def http(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", JWT_SECRET)
    return TestClient(app, raise_server_exceptions=False)


def save(http, **body):
    payload = {"monthly_budget": 100, **body}
    return http.post("/budget/config", json=payload, headers={"Authorization": f"Bearer {token()}"})


@pytest.mark.parametrize("field", ["alert_webhook_url", "slack_webhook_url", "discord_webhook_url"])
@pytest.mark.parametrize(
    "url",
    [
        "https://169.254.169.254/latest/meta-data/",
        "https://[::ffff:169.254.169.254]/",
        "https://127.0.0.1/x",
        "https://10.0.0.5/x",
        "https://localhost/x",
        "http://hooks.example.com/x",
        "https://rebind.example.com/x",
    ],
)
def test_saving_an_unsafe_webhook_is_refused_and_nothing_is_stored(http, field, url):
    db = MagicMock()
    with patch("app.services.budget_alerting.get_supabase_client", return_value=db):
        response = save(http, **{field: url})
    assert response.status_code == 400
    db.client.table.assert_not_called()
    assert "169.254" not in response.text and "10.0.0" not in response.text


def test_saving_a_public_https_webhook_works(http):
    db = MagicMock()
    with patch("app.services.budget_alerting.get_supabase_client", return_value=db):
        response = save(http, alert_webhook_url="https://hooks.example.com/services/abc")
    assert response.status_code == 200
    assert response.json()["alert_webhook_url"] == "https://hooks.example.com/services/abc"
    db.client.table.assert_called_once()
