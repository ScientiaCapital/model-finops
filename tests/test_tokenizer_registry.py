"""Tokenizer downloads are restricted to an allowlist of plain Hugging Face repo ids."""

import threading
import time
from unittest.mock import AsyncMock, patch

import pytest

from app import tokenizer_registry as registry
from app.main import routing_service

DEFAULT_ID = "UW/OLMo2-8B-SuperBPE-t180k"


class FakeTokenizer:
    def __init__(self, repo_id):
        self.repo_id = repo_id

    def __call__(self, text, **kwargs):
        return {"input_ids": list(range(len(text.split())))}


@pytest.fixture(autouse=True)
def clean_registry(monkeypatch):
    monkeypatch.delenv("ALLOWED_TOKENIZERS", raising=False)
    registry._cache.clear()
    yield
    registry._cache.clear()


@pytest.fixture
def fake_loader():
    with patch.object(registry, "_load_tokenizer", side_effect=FakeTokenizer) as loader:
        yield loader


@pytest.mark.parametrize(
    "bad",
    [
        "/etc/passwd",
        "./local/tokenizer",
        "../secrets/model",
        "../../x",
        "a/b/c",
        "no-slash",
        "~/models/x",
        "C:\\models\\x",
        "https://evil.example/x/y",
        "org/name with space",
        "org/..",
        "./x",
        "org/name;rm",
        "",
    ],
)
def test_malformed_ids_are_refused_before_any_load(bad, fake_loader, monkeypatch):
    monkeypatch.setenv("ALLOWED_TOKENIZERS", bad)  # even if an operator listed it
    with pytest.raises(registry.TokenizerNotAllowedError):
        registry.validate_tokenizer_id(bad)
    with pytest.raises(registry.TokenizerNotAllowedError):
        registry.get_tokenizer(bad)
    fake_loader.assert_not_called()


def test_well_formed_but_unlisted_id_is_refused(fake_loader):
    with pytest.raises(registry.TokenizerNotAllowedError):
        registry.get_tokenizer("someone/other-tokenizer")
    fake_loader.assert_not_called()


def test_built_in_default_is_allowed(fake_loader):
    assert registry.get_tokenizer(DEFAULT_ID).repo_id == DEFAULT_ID


def test_env_allowlist_extends_defaults(monkeypatch, fake_loader):
    monkeypatch.setenv("ALLOWED_TOKENIZERS", " gpt2/tok , org/model-1.0 ")
    assert registry.get_tokenizer("org/model-1.0").repo_id == "org/model-1.0"
    assert registry.get_tokenizer("gpt2/tok").repo_id == "gpt2/tok"
    assert registry.get_tokenizer(DEFAULT_ID)


def test_cache_is_bounded_and_lru(monkeypatch, fake_loader):
    ids = [f"org/tok-{i}" for i in range(registry.MAX_CACHED + 2)]
    monkeypatch.setenv("ALLOWED_TOKENIZERS", ",".join(ids))
    for repo_id in ids[: registry.MAX_CACHED]:
        registry.get_tokenizer(repo_id)
    registry.get_tokenizer(ids[0])  # touch: ids[1] is now the oldest
    registry.get_tokenizer(ids[-2])
    registry.get_tokenizer(ids[-1])
    assert len(registry._cache) == registry.MAX_CACHED
    assert ids[0] in registry._cache
    assert ids[1] not in registry._cache


def test_download_does_not_hold_the_lock(monkeypatch):
    monkeypatch.setenv("ALLOWED_TOKENIZERS", "org/slow,org/fast")
    started = threading.Event()
    release = threading.Event()

    def loader(repo_id):
        if repo_id == "org/slow":
            started.set()
            release.wait(5)
        return FakeTokenizer(repo_id)

    results = {}
    with patch.object(registry, "_load_tokenizer", side_effect=loader):
        slow = threading.Thread(
            target=lambda: results.setdefault("slow", registry.get_tokenizer("org/slow"))
        )
        slow.start()
        assert started.wait(5)
        t0 = time.monotonic()
        fast = registry.get_tokenizer("org/fast")  # would block on a global lock held in download
        elapsed = time.monotonic() - t0
        release.set()
        slow.join(5)
    assert fast.repo_id == "org/fast"
    assert elapsed < 1.0
    assert results["slow"].repo_id == "org/slow"


def test_estimate_without_id_returns_none(fake_loader):
    assert registry.estimate_tokenization_metrics("hello", None) is None


def test_complete_rejects_disallowed_tokenizer_with_400(client, monkeypatch):
    monkeypatch.setenv("ALLOW_ANONYMOUS", "true")
    with (
        patch.object(routing_service, "route_and_complete", new_callable=AsyncMock) as route,
        patch.object(registry, "_load_tokenizer") as loader,
    ):
        for bad in ("/etc/passwd", "../x/y", "someone/unlisted"):
            response = client.post("/complete", json={"prompt": "hi", "tokenizer_id": bad})
            assert response.status_code == 400, (bad, response.text)
    route.assert_not_awaited()
    loader.assert_not_called()
