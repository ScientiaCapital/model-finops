"""Stripe webhook errors and encryption configuration fail with generic, loud behavior."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.billing.webhook_handler import WebhookHandler
from app.services import encryption_service as enc


def _handler(verify_error):
    stripe = MagicMock()
    stripe.verify_webhook_signature.side_effect = verify_error
    handler = WebhookHandler.__new__(WebhookHandler)
    handler.stripe = stripe
    handler.webhook_secret = "whsec_test"
    return handler


async def test_webhook_signature_failure_is_generic_and_logged(caplog):
    secret_text = "No signatures found matching the expected signature for payload whsec_leak"
    handler = _handler(ValueError(secret_text))
    request = MagicMock()
    request.body = AsyncMock(return_value=b"{}")
    request.headers = {"Stripe-Signature": "t=1,v1=abc"}
    with caplog.at_level(logging.ERROR), pytest.raises(HTTPException) as exc:
        await handler.handle_webhook(request)
    assert exc.value.status_code == 400
    assert exc.value.detail == "invalid webhook signature"
    assert "whsec_leak" not in str(exc.value.detail)
    assert "whsec_leak" in caplog.text


async def test_webhook_processing_failure_is_generic_and_logged(caplog):
    handler = _handler(None)
    handler.stripe.verify_webhook_signature.side_effect = None
    handler.stripe.verify_webhook_signature.return_value = MagicMock(id="evt_1", type="x.y")
    handler._is_event_processed = AsyncMock(return_value=False)
    handler._log_event = AsyncMock()
    handler._record_event_error = AsyncMock()
    handler._process_event = AsyncMock(side_effect=RuntimeError("row 42 of customers: pg_secret"))
    request = MagicMock()
    request.body = AsyncMock(return_value=b"{}")
    request.headers = {"Stripe-Signature": "t=1,v1=abc"}
    with caplog.at_level(logging.ERROR), pytest.raises(HTTPException) as exc:
        await handler.handle_webhook(request)
    assert exc.value.status_code == 500
    assert exc.value.detail == "error processing event"
    assert "pg_secret" in caplog.text


def test_missing_key_raises_clear_error_on_use(monkeypatch):
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    service = enc.EncryptionService()  # constructing must not fail: the key is needed on use
    with pytest.raises(enc.EncryptionConfigError, match="ENCRYPTION_KEY"):
        service.encrypt("sk-test")
    with pytest.raises(enc.EncryptionConfigError, match="ENCRYPTION_KEY"):
        service.decrypt("AAAA")


def test_empty_key_is_treated_as_missing(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", "")
    with pytest.raises(enc.EncryptionConfigError):
        enc.EncryptionService().encrypt("x")


def test_explicit_key_works_without_env(monkeypatch):
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    service = enc.EncryptionService(key="k" * 32)
    assert service.decrypt(service.encrypt("secret")) == "secret"


def test_two_services_with_same_env_key_interoperate(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", "e" * 32)
    assert enc.EncryptionService().decrypt(enc.EncryptionService().encrypt("v")) == "v"


def test_no_base64_only_fallback_remains():
    assert not hasattr(enc, "CRYPTOGRAPHY_AVAILABLE")
    assert not hasattr(enc.EncryptionService("k" * 32), "_use_fallback")
