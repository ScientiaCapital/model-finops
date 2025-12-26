"""
API Key Authentication Middleware

Validates API keys in the X-API-Key header and attaches user context to requests.
Works alongside JWT authentication - users can use either method.

Authentication Flow:
1. Check for X-API-Key header
2. If present, validate the key and check rate limits
3. Attach user context to request.state
4. After response, record usage metrics

Rate Limiting:
- Per-minute and per-day limits are enforced
- 429 Too Many Requests returned when limits exceeded
- Retry-After header indicates when to retry
"""

import time
import uuid
import logging
from typing import List, Optional, Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.types import ASGIApp

from app.services.api_key_service import APIKeyService
from app.database.supabase_client import SupabaseClient

logger = logging.getLogger(__name__)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    Middleware for API key authentication and rate limiting.

    This middleware intercepts requests with X-API-Key headers,
    validates the keys, enforces rate limits, and records usage.

    The APIKeyService is lazily loaded from app.state.supabase_client,
    allowing the middleware to be added before the service is initialized.

    Usage in main.py:
        from app.middleware import APIKeyMiddleware

        app.add_middleware(
            APIKeyMiddleware,
            protected_paths=["/v1/", "/api/"],
            exclude_paths=["/health", "/docs", "/openapi.json"],
        )

        # In lifespan handler:
        app.state.supabase_client = supabase_client
    """

    def __init__(
        self,
        app: ASGIApp,
        protected_paths: Optional[List[str]] = None,
        exclude_paths: Optional[List[str]] = None,
    ):
        """
        Initialize the API key middleware.

        Args:
            app: The ASGI application
            protected_paths: Path prefixes that require API key auth
                             (default: None = check all paths)
            exclude_paths: Path prefixes to skip (e.g., /health, /docs)

        Note: APIKeyService is lazily loaded from app.state.supabase_client
        at request time, allowing the middleware to be added at startup.
        """
        super().__init__(app)
        self._api_key_service: Optional[APIKeyService] = None
        self.protected_paths = protected_paths or []
        self.exclude_paths = exclude_paths or [
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/favicon.ico",
        ]

    def _get_api_key_service(self, request: Request) -> Optional[APIKeyService]:
        """Get or create API key service (lazy loading)."""
        if self._api_key_service is not None:
            return self._api_key_service

        supabase = getattr(request.app.state, "supabase_client", None)
        if supabase is None:
            return None

        self._api_key_service = APIKeyService(supabase)
        return self._api_key_service

    def _should_check_api_key(self, path: str) -> bool:
        """
        Determine if a path requires API key authentication.

        Returns True if:
        - Path is not in exclude_paths
        - AND (protected_paths is empty OR path starts with a protected prefix)
        """
        # Skip excluded paths
        for exclude in self.exclude_paths:
            if path.startswith(exclude):
                return False

        # If no protected_paths specified, check all paths
        if not self.protected_paths:
            return True

        # Check if path matches any protected prefix
        for protected in self.protected_paths:
            if path.startswith(protected):
                return True

        return False

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request, validating API keys when required.

        Flow:
        1. Check if path requires API key auth
        2. Get API key service (lazy loading)
        3. Extract X-API-Key header
        4. Validate key and check rate limits
        5. Attach user context to request.state
        6. Call the actual endpoint
        7. Record usage metrics
        """
        path = request.url.path
        start_time = time.time()
        request_id = str(uuid.uuid4())

        # Add request ID for tracing
        request.state.request_id = request_id

        # Skip if path doesn't require API key auth
        if not self._should_check_api_key(path):
            return await call_next(request)

        # Get API key service (lazy loading)
        api_key_service = self._get_api_key_service(request)
        if api_key_service is None:
            # Service not initialized yet, skip API key auth
            return await call_next(request)

        # Check for API key header
        api_key = request.headers.get("X-API-Key")

        # If no API key but has Authorization header, let JWT auth handle it
        if not api_key:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                # JWT auth will handle this request
                return await call_next(request)
            elif self.protected_paths and any(path.startswith(p) for p in self.protected_paths):
                # Protected path with no auth - return 401
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": "authentication_required",
                        "message": "API key or Bearer token required",
                        "hint": "Add X-API-Key header or Authorization: Bearer <token>",
                    },
                )
            else:
                # Not protected, continue without auth
                return await call_next(request)

        # Validate the API key
        validation = await api_key_service.validate_key(api_key)

        if not validation.is_valid:
            logger.warning(f"Invalid API key attempt on {path}: {validation.error_message}")
            return JSONResponse(
                status_code=401,
                content={
                    "error": "invalid_api_key",
                    "message": validation.error_message or "Invalid or expired API key",
                },
            )

        # Check rate limits
        rate_limit = await api_key_service.check_rate_limit(validation.key_id)

        if not rate_limit.is_allowed:
            logger.warning(
                f"Rate limit exceeded for key {validation.key_id[:8]}... "
                f"({rate_limit.requests_this_minute}/min, {rate_limit.requests_today}/day)"
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": "Too many requests",
                    "retry_after": rate_limit.retry_after_seconds,
                    "limits": {
                        "minute": {
                            "used": rate_limit.requests_this_minute,
                            "limit": rate_limit.minute_limit,
                        },
                        "day": {
                            "used": rate_limit.requests_today,
                            "limit": rate_limit.day_limit,
                        },
                    },
                },
                headers={"Retry-After": str(rate_limit.retry_after_seconds)},
            )

        # Attach user context to request.state for use in endpoints
        request.state.api_key_id = validation.key_id
        request.state.user_id = validation.user_id
        request.state.api_key_permissions = validation.permissions
        request.state.auth_method = "api_key"

        logger.debug(
            f"API key auth successful: user={validation.user_id[:8]}... "
            f"key={validation.key_id[:8]}... path={path}"
        )

        # Process the request
        response = await call_next(request)

        # Record usage (async, non-blocking)
        latency_ms = (time.time() - start_time) * 1000

        # Get token counts from response headers if available
        tokens_in = int(response.headers.get("X-Tokens-In", 0))
        tokens_out = int(response.headers.get("X-Tokens-Out", 0))
        cost_usd = float(response.headers.get("X-Cost-USD", 0))

        # Record in background (don't wait)
        try:
            await api_key_service.record_usage(
                key_id=validation.key_id,
                user_id=validation.user_id,
                endpoint=path,
                method=request.method,
                status_code=response.status_code,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                ip_address=self._get_client_ip(request),
                user_agent=request.headers.get("User-Agent"),
                request_id=request_id,
            )
        except Exception as e:
            # Don't fail the request if usage recording fails
            logger.error(f"Failed to record API key usage: {e}")

        return response

    def _get_client_ip(self, request: Request) -> Optional[str]:
        """Extract client IP address from request headers."""
        # Check common proxy headers first
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For can contain multiple IPs, use the first (client)
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to direct client IP
        if request.client:
            return request.client.host

        return None


# =============================================================================
# Dependency for endpoints that need API key context
# =============================================================================

def get_api_key_context(request: Request) -> dict:
    """
    FastAPI dependency to get API key context from request.

    Use this in endpoints that need access to API key information.

    Usage:
        @app.get("/some-endpoint")
        async def endpoint(api_context: dict = Depends(get_api_key_context)):
            key_id = api_context.get("api_key_id")
            user_id = api_context.get("user_id")
            permissions = api_context.get("permissions", [])
    """
    return {
        "api_key_id": getattr(request.state, "api_key_id", None),
        "user_id": getattr(request.state, "user_id", None),
        "permissions": getattr(request.state, "api_key_permissions", []),
        "auth_method": getattr(request.state, "auth_method", None),
        "request_id": getattr(request.state, "request_id", None),
    }
