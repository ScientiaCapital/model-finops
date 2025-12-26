"""
Quota Enforcement Middleware

Enforces subscription quota limits before processing API requests.
Returns 429 Too Many Requests when quota is exceeded with upgrade prompt.

Flow:
1. Check if path requires quota enforcement (/chat, /complete, /v1/)
2. Get user ID from request state (set by auth middleware)
3. Check quota via billing service
4. If exceeded, return 429 with upgrade URL
5. If allowed, process request and record usage after response

Usage in main.py:
    from app.middleware.quota_enforcement import QuotaEnforcementMiddleware

    app.add_middleware(
        QuotaEnforcementMiddleware,
        billing_service=billing_service,
        protected_paths=["/chat", "/complete", "/v1/"],
        exclude_paths=["/health", "/docs"],
    )
"""

import time
import logging
from typing import List, Optional, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.types import ASGIApp

from app.services.billing_service import BillingService

logger = logging.getLogger(__name__)


class QuotaEnforcementMiddleware(BaseHTTPMiddleware):
    """
    Middleware for enforcing subscription quota limits.

    Checks user's remaining quota before processing requests
    and records usage after successful responses.

    The billing_service is lazily loaded from app.state.billing_service,
    allowing the middleware to be added before the service is initialized.
    """

    def __init__(
        self,
        app: ASGIApp,
        protected_paths: Optional[List[str]] = None,
        exclude_paths: Optional[List[str]] = None,
    ):
        """
        Initialize quota enforcement middleware.

        Args:
            app: The ASGI application
            protected_paths: Path prefixes that require quota check
                             (default: ["/chat", "/complete", "/v1/"])
            exclude_paths: Path prefixes to skip (e.g., /health, /docs)

        Note: billing_service is loaded from app.state.billing_service
        at request time, allowing lazy initialization.
        """
        super().__init__(app)
        self.protected_paths = protected_paths or ["/chat", "/complete", "/v1/"]
        self.exclude_paths = exclude_paths or [
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/favicon.ico",
            "/billing",  # Billing endpoints don't consume quota
            "/api-keys",  # API key management doesn't consume quota
        ]

    def _get_billing_service(self, request: Request) -> Optional[BillingService]:
        """Get billing service from app state (lazy loading)."""
        return getattr(request.app.state, "billing_service", None)

    def _should_check_quota(self, path: str, method: str) -> bool:
        """
        Determine if a path requires quota enforcement.

        Only enforces quota on POST requests to protected paths.
        GET requests (like fetching status) don't consume tokens.

        Returns True if:
        - Path is not in exclude_paths
        - Method is POST (or PUT/PATCH for some endpoints)
        - Path starts with a protected prefix
        """
        # Skip excluded paths
        for exclude in self.exclude_paths:
            if path.startswith(exclude):
                return False

        # Only enforce on write operations
        if method not in ("POST", "PUT", "PATCH"):
            return False

        # Check if path matches any protected prefix
        for protected in self.protected_paths:
            if path.startswith(protected):
                return True

        return False

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request, enforcing quota limits.

        Flow:
        1. Check if path requires quota enforcement
        2. Get billing service (lazy loading from app.state)
        3. Get user_id from request state
        4. Check quota
        5. If exceeded, return 429
        6. Process request
        7. Record usage from response headers
        """
        path = request.url.path
        method = request.method
        start_time = time.time()

        # Skip if path doesn't require quota enforcement
        if not self._should_check_quota(path, method):
            return await call_next(request)

        # Get billing service (lazy loading)
        billing = self._get_billing_service(request)
        if billing is None:
            # Billing not initialized yet, skip quota enforcement
            return await call_next(request)

        # Get user_id from request state (set by auth middleware)
        user_id = getattr(request.state, "user_id", None)

        # If no user_id, let auth middleware handle it
        if not user_id:
            return await call_next(request)

        # Check quota
        try:
            quota = await billing.check_quota(user_id)
        except Exception as e:
            logger.error(f"Failed to check quota for user {user_id[:8]}...: {e}")
            # Fail open - don't block requests on quota check errors
            return await call_next(request)

        # If quota exceeded, return 429
        if not quota.has_quota:
            logger.warning(
                f"Quota exceeded for user {user_id[:8]}... "
                f"({quota.tokens_used}/{quota.tokens_limit} tokens, tier={quota.tier})"
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "quota_exceeded",
                    "message": "Monthly token quota exceeded",
                    "details": {
                        "tokens_used": quota.tokens_used,
                        "tokens_limit": quota.tokens_limit,
                        "tier": quota.tier,
                        "period_ends_at": quota.period_ends_at.isoformat(),
                    },
                    "upgrade_url": quota.upgrade_url or "/billing/upgrade",
                    "hint": "Upgrade your plan for more tokens or wait until next billing period",
                },
                headers={
                    "Retry-After": str(int((quota.period_ends_at - time.time()).total_seconds()))
                    if hasattr(quota.period_ends_at, "total_seconds") else "3600",
                    "X-Quota-Remaining": "0",
                    "X-Quota-Limit": str(quota.tokens_limit),
                },
            )

        # Add quota info to request state for downstream use
        request.state.quota_status = quota

        # Process the request
        response = await call_next(request)

        # Record usage from response headers
        latency_ms = (time.time() - start_time) * 1000

        # Get token counts from response headers if available
        tokens_in = int(response.headers.get("X-Tokens-In", 0))
        tokens_out = int(response.headers.get("X-Tokens-Out", 0))
        total_tokens = tokens_in + tokens_out
        cost_cents = int(float(response.headers.get("X-Cost-USD", 0)) * 100)
        provider = response.headers.get("X-Provider")
        model = response.headers.get("X-Model")
        is_cache_hit = response.headers.get("X-Cache-Hit", "").lower() == "true"

        # Only record usage for successful responses with tokens
        if response.status_code < 400 and total_tokens > 0:
            try:
                updated_quota = await billing.record_usage(
                    user_id=user_id,
                    tokens=total_tokens,
                    cost_cents=cost_cents,
                    provider=provider,
                    model=model,
                    is_cache_hit=is_cache_hit,
                )

                # Add usage info to response headers
                response.headers["X-Quota-Used"] = str(updated_quota.tokens_used)
                response.headers["X-Quota-Remaining"] = str(updated_quota.tokens_remaining)
                response.headers["X-Quota-Limit"] = str(updated_quota.tokens_limit)

                logger.debug(
                    f"Recorded usage for user {user_id[:8]}...: "
                    f"{total_tokens} tokens, {updated_quota.tokens_remaining} remaining"
                )
            except Exception as e:
                # Don't fail the request if usage recording fails
                logger.error(f"Failed to record usage: {e}")

        return response


# =============================================================================
# Utility Functions
# =============================================================================

def get_quota_status(request: Request) -> Optional[dict]:
    """
    FastAPI dependency to get quota status from request.

    Usage:
        @app.get("/some-endpoint")
        async def endpoint(quota: dict = Depends(get_quota_status)):
            remaining = quota.get("tokens_remaining", 0)
    """
    quota = getattr(request.state, "quota_status", None)
    if not quota:
        return None

    return {
        "has_quota": quota.has_quota,
        "tokens_used": quota.tokens_used,
        "tokens_limit": quota.tokens_limit,
        "tokens_remaining": quota.tokens_remaining,
        "usage_percentage": quota.usage_percentage,
        "tier": quota.tier,
        "period_ends_at": quota.period_ends_at.isoformat() if quota.period_ends_at else None,
    }
