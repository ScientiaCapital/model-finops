"""The semantic cache never serves one caller's response to another caller."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.database.cost_tracker_async import AsyncCostTracker
from app.services.routing_service import RoutingService

STORE_ARGS = {
    "prompt": "What is Python?",
    "max_tokens": 100,
    "response": "A language.",
    "provider": "claude",
    "model": "m",
    "complexity": "simple",
    "tokens_in": 3,
    "tokens_out": 2,
    "cost": 0.01,
}


class FakeEmbeddings:
    def generate_embedding(self, text):
        return [0.1, 0.2, 0.3]


class FakeCacheDB:
    """In-memory stand-in for the response_cache table with per-user search."""

    def __init__(self):
        self.rows = []
        self.searches = []
        self.upserts = []

    async def upsert(self, table, data, on_conflict=None, use_admin=False):
        self.upserts.append(data)
        self.rows.append(dict(data))
        return [data]

    async def semantic_search(
        self, query_embedding, match_threshold, match_count, user_id=None, **kw
    ):
        self.searches.append(user_id)
        # Mirrors match_cache_entries_v2: a NULL target_user_id would match every row, so
        # the application must never ask that question.
        hits = [r for r in self.rows if user_id is None or r["user_id"] == user_id]
        return [dict(r, similarity=1.0) for r in hits[:match_count]]

    async def select(self, *a, **kw):
        return [{"hit_count": 0}]

    async def update(self, *a, **kw):
        return []


@pytest.fixture
def db():
    return FakeCacheDB()


@pytest.fixture
def patched(db):
    with (
        patch("app.database.cost_tracker_async.get_supabase_client", return_value=db),
        patch(
            "app.database.cost_tracker_async.get_embedding_generator", return_value=FakeEmbeddings()
        ),
    ):
        yield


async def test_anonymous_tracker_never_reads_or_writes_cache(patched, db):
    anonymous = AsyncCostTracker(user_id=None)
    assert await anonymous.store_in_cache(**STORE_ARGS) == {}
    assert db.upserts == []
    db.rows.append({"user_id": "user-a", "prompt_normalized": "x", "cache_key": "k"})
    assert await anonymous.check_cache("What is Python?", 100) is None
    assert db.searches == []


async def test_user_b_never_gets_user_a_cached_response(patched, db):
    await AsyncCostTracker(user_id="user-a").store_in_cache(**STORE_ARGS)
    assert db.upserts[0]["user_id"] == "user-a"

    assert await AsyncCostTracker(user_id="user-b").check_cache("What is Python?", 100) is None
    hit = await AsyncCostTracker(user_id="user-a").check_cache("What is Python?", 100)
    assert hit is not None
    assert hit["response"] == "A language."


class CountingProvider:
    MODEL = "fake-model"

    def __init__(self):
        self.calls = 0

    async def complete(self, prompt, max_tokens=1000):
        self.calls += 1
        return f"answer {self.calls}", 3, 2, 0.0


async def test_routing_service_scopes_cache_to_the_caller(patched, db):
    provider = CountingProvider()
    service = RoutingService(providers={"claude": provider}, user_id=None)
    service.cost_tracker.log_request = AsyncMock(return_value={})
    service.cost_tracker.get_total_cost = AsyncMock(return_value=0.0)
    for tracker_cls_patch in (
        patch.object(AsyncCostTracker, "log_request", AsyncMock(return_value={})),
        patch.object(AsyncCostTracker, "get_total_cost", AsyncMock(return_value=0.0)),
        patch.object(AsyncCostTracker, "record_cache_hit", AsyncMock()),
    ):
        tracker_cls_patch.start()
    try:
        a1 = await service.route_and_complete("What is Python?", False, 100, user_id="user-a")
        b1 = await service.route_and_complete("What is Python?", False, 100, user_id="user-b")
        a2 = await service.route_and_complete("What is Python?", False, 100, user_id="user-a")
        anon = await service.route_and_complete("What is Python?", False, 100, user_id=None)
    finally:
        patch.stopall()

    assert a1["cache_hit"] is False
    assert b1["cache_hit"] is False and b1["response"] == "answer 2"
    assert a2["cache_hit"] is True and a2["response"] == "answer 1"
    assert anon["cache_hit"] is False and anon["response"] == "answer 3"
    assert provider.calls == 3
    assert {r["user_id"] for r in db.rows} == {"user-a", "user-b"}
    assert None not in db.searches


async def test_cache_write_failure_does_not_fail_the_request(patched, db):
    db.upsert = AsyncMock(side_effect=RuntimeError("rls says no"))
    service = RoutingService(providers={"claude": CountingProvider()}, user_id=None)
    with (
        patch.object(AsyncCostTracker, "log_request", AsyncMock(return_value={})),
        patch.object(AsyncCostTracker, "get_total_cost", AsyncMock(return_value=0.0)),
    ):
        result = await service.route_and_complete("Hello there", False, 50, user_id="user-a")
    assert result["response"] == "answer 1"
    assert MagicMock  # keep import used


class PrimaryKeyCacheDB(FakeCacheDB):
    """Like the real table: cache_key is the primary key, so an upsert replaces that row."""

    async def upsert(self, table, data, on_conflict=None, use_admin=False):
        rows = data if isinstance(data, list) else [data]
        for row in rows:
            self.upserts.append(row)
            self.rows = [r for r in self.rows if r["cache_key"] != row["cache_key"]]
            self.rows.append(dict(row))
        return rows


async def test_same_prompt_from_two_users_gets_two_different_cache_keys():
    db = PrimaryKeyCacheDB()
    with (
        patch("app.database.cost_tracker_async.get_supabase_client", return_value=db),
        patch(
            "app.database.cost_tracker_async.get_embedding_generator", return_value=FakeEmbeddings()
        ),
    ):
        await AsyncCostTracker(user_id="user-a").store_in_cache(**STORE_ARGS)
        await AsyncCostTracker(user_id="user-b").store_in_cache(**STORE_ARGS)
        await AsyncCostTracker(user_id="user-a").store_in_cache(**STORE_ARGS)

    keys = {u["user_id"]: u["cache_key"] for u in db.upserts}
    assert keys["user-a"] != keys["user-b"]
    # B's write must not have replaced A's row
    assert {r["user_id"] for r in db.rows} == {"user-a", "user-b"}
    assert len(db.rows) == 2


async def test_cache_key_returned_to_the_caller_is_the_key_that_was_stored(patched, db):
    """/feedback looks a row up by this key, so it must be the stored primary key."""
    service = RoutingService(providers={"claude": CountingProvider()}, user_id=None)
    with (
        patch.object(AsyncCostTracker, "log_request", AsyncMock(return_value={})),
        patch.object(AsyncCostTracker, "get_total_cost", AsyncMock(return_value=0.0)),
    ):
        result = await service.route_and_complete("What is Python?", False, 100, user_id="user-a")
    assert result["cache_key"] == db.upserts[0]["cache_key"]
