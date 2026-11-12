"""Startup and shutdown run cleanly offline (no provider keys, no Supabase, no embeddings extra)."""

from fastapi.testclient import TestClient

from app.main import app


def test_lifespan_shutdown_completes(caplog):
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
    assert "Shutdown complete" in caplog.text
