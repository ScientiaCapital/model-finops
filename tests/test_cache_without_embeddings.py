"""The semantic cache is optional: without the `embeddings` extra, reads and writes are skipped.

sentence-transformers is blocked in sys.modules so the real EmbeddingGenerator raises the same
ImportError it raises when the extra is not installed.
"""

import logging
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.database.cost_tracker_async import AsyncCostTracker
from app.embeddings import EmbeddingGenerator
from app.main import routing_service

CACHE_LOGGER = "app.database.cost_tracker_async"

# These tests exercise caching and routing, not authentication, so anonymous /complete is on.
pytestmark = pytest.mark.usefixtures("allow_anonymous")


@pytest.fixture
def no_sentence_transformers():
    with patch.dict(sys.modules, {"sentence_transformers": None}):
        yield


@pytest.fixture
def fake_db():
    db = MagicMock()
    db.upsert = AsyncMock(return_value=[{"cache_key": "x"}])
    db.semantic_search = AsyncMock(return_value=[])
    return db


@pytest.fixture
def tracker(no_sentence_transformers, fake_db):
    with (
        patch("app.database.cost_tracker_async.get_supabase_client", return_value=fake_db),
        patch(
            "app.database.cost_tracker_async.get_embedding_generator",
            return_value=EmbeddingGenerator(),
        ),
    ):
        yield AsyncCostTracker(user_id="user-a")  # anonymous callers skip the cache earlier


STORE_ARGS = {
    "prompt": "What is Python?",
    "max_tokens": 100,
    "response": "A language.",
    "provider": "claude",
    "model": "claude-3-haiku-20240307",
    "complexity": "simple",
    "tokens_in": 3,
    "tokens_out": 2,
    "cost": 0.0,
}


async def test_read_path_skips_cache_without_embeddings(tracker, fake_db):
    assert await tracker.check_cache("What is Python?", 100) is None
    fake_db.semantic_search.assert_not_awaited()


async def test_write_path_skips_cache_without_embeddings(tracker, fake_db):
    assert await tracker.store_in_cache(**STORE_ARGS) == {}
    fake_db.upsert.assert_not_awaited()


async def test_missing_embeddings_logged_once_at_info(tracker, caplog):
    with caplog.at_level(logging.DEBUG, logger=CACHE_LOGGER):
        await tracker.check_cache("What is Python?", 100)
        await tracker.store_in_cache(**STORE_ARGS)
        await tracker.store_in_cache(**STORE_ARGS)
        await tracker.check_cache("What is Python?", 100)

    notices = [r for r in caplog.records if "semantic cache disabled" in r.getMessage()]
    assert [r.levelno for r in notices] == [logging.INFO]
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


def test_complete_succeeds_without_embeddings(
    client, mock_jwt_token, no_sentence_transformers, fake_db
):
    class FakeProvider:
        MODEL = "fake-model"

        async def complete(self, prompt, max_tokens=1000):
            return "fake answer", 3, 2, 0.0

    with (
        patch.dict("os.environ", {"SUPABASE_JWT_SECRET": "test-jwt-secret-for-testing-only"}),
        patch.object(routing_service, "providers", {"claude": FakeProvider()}),
        patch("app.database.cost_tracker_async.get_supabase_client", return_value=fake_db),
        patch(
            "app.database.cost_tracker_async.get_embedding_generator",
            return_value=EmbeddingGenerator(),
        ),
        patch.object(AsyncCostTracker, "log_request", AsyncMock(return_value={})),
        patch.object(AsyncCostTracker, "get_total_cost", AsyncMock(return_value=0.0)),
    ):
        response = client.post(
            "/complete",
            json={"prompt": "What is Python?", "max_tokens": 50},
            headers={"Authorization": f"Bearer {mock_jwt_token}"},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["response"] == "fake answer"
    assert body["cache_hit"] is False
    fake_db.semantic_search.assert_not_awaited()
    fake_db.upsert.assert_not_awaited()
