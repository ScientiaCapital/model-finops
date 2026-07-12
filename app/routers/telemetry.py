"""
Telemetry Ingest Router - Accept pre-computed usage events from external tools.

Unlike POST /complete (which performs the LLM call itself), this endpoint
accepts an already-finished completion's usage data for logging only — e.g.
from silkroute reporting its own Ollama-routed AV demo runs. Machine-to-machine
only: authenticated via a shared-secret bearer token (FINOPS_INGEST_TOKEN), not
the Supabase-user JWT auth used elsewhere in this app.

Endpoints:
- POST /api/telemetry/ingest - Log a pre-computed usage event
"""

import os
import secrets
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.database.cost_tracker_async import AsyncCostTracker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])

# Admin-mode instance (user_id=None) — writes to the same table/rows that
# GET /stats and the dashboard already read from, matching main.py's own
# module-level routing_service.cost_tracker.
_cost_tracker = AsyncCostTracker(user_id=None)


class TelemetryEvent(BaseModel):
    provider: str = Field(..., description="Provider name, e.g. 'ollama'")
    model: str = Field(..., description="Model identifier, e.g. 'ollama/qwen2.5:14b'")
    input_tokens: int = Field(..., ge=0)
    output_tokens: int = Field(..., ge=0)
    cost_usd: float = Field(..., ge=0.0)
    task_type: Optional[str] = Field(None, description="Short task/label string")
    session_id: Optional[str] = None
    project_id: Optional[str] = None
    latency_ms: Optional[int] = Field(None, ge=0)
    timestamp: Optional[str] = Field(None, description="ISO timestamp of the original event")
    source: Optional[str] = Field(None, description="Origin label, e.g. 'silkroute'")


def _verify_ingest_token(request: Request) -> None:
    expected = os.getenv("FINOPS_INGEST_TOKEN", "")
    auth_header = request.headers.get("Authorization", "")
    got = auth_header.removeprefix("Bearer ") if auth_header.startswith("Bearer ") else ""
    if not expected or not got or not secrets.compare_digest(got, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing ingest token")


@router.post("/ingest")
async def ingest_usage_event(event: TelemetryEvent, request: Request) -> dict:
    """Log a pre-computed usage event from an external caller (e.g. silkroute)."""
    _verify_ingest_token(request)

    result = await _cost_tracker.log_request(
        prompt=event.task_type or "",
        complexity="external",
        provider=event.provider,
        model=event.model,
        tokens_in=event.input_tokens,
        tokens_out=event.output_tokens,
        cost=event.cost_usd,
        project_id=event.project_id,
        session_id=event.session_id,
        task_type=event.task_type,
        latency_ms=event.latency_ms,
        source=event.source or "external",
        timestamp=event.timestamp,
    )

    logger.info(f"Telemetry event ingested: {event.provider}/{event.model}")
    return {"status": "logged", "row": result}
