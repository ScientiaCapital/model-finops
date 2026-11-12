"""Authentication middleware and dependencies for Supabase JWT validation."""

import hmac
import logging
import os

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWTError

logger = logging.getLogger(__name__)

# HTTP Bearer token scheme
security = HTTPBearer()


def get_jwt_secret() -> str | None:
    """
    Get Supabase JWT secret from environment.

    Read dynamically to allow test fixtures to override the value.

    Returns:
        JWT secret string or None if not set
    """
    return os.getenv("SUPABASE_JWT_SECRET")


def verify_jwt_token(token: str) -> dict:
    """
    Verify and decode Supabase JWT token.

    Args:
        token: JWT token string from Authorization header

    Returns:
        Decoded token payload with user_id, email, role, etc.

    Raises:
        HTTPException: If token is invalid or expired
    """
    jwt_secret = get_jwt_secret()
    if not jwt_secret:
        logger.error("SUPABASE_JWT_SECRET not set in environment!")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Server authentication configuration error",
        )

    try:
        # Decode JWT using Supabase secret
        payload = jwt.decode(
            token,
            jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",  # Supabase sets aud to "authenticated"
            options={"require": ["exp", "sub"]},  # a token without expiry or subject is refused
        )

        logger.debug(f"JWT verified for user: {payload.get('sub')}")

        return payload

    except jwt.ExpiredSignatureError:
        logger.warning("JWT token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    except jwt.InvalidAudienceError:
        logger.warning("JWT audience mismatch")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token audience",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    except PyJWTError as e:
        logger.warning(f"JWT validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    FastAPI dependency to get current authenticated user from JWT.

    Validates the JWT token and returns the payload.

    Usage:
        @app.get("/protected")
        async def protected_endpoint(user: dict = Depends(get_current_user)):
            user_id = user["sub"]  # Supabase user ID
            email = user["email"]
            return {"message": f"Hello {email}"}

    Args:
        credentials: HTTP Bearer credentials (auto-injected by FastAPI)

    Returns:
        Decoded JWT payload with user info

    Raises:
        HTTPException: If authentication fails
    """
    token = credentials.credentials
    return verify_jwt_token(token)


def get_current_user_id(user: dict = Depends(get_current_user)) -> str:
    """
    FastAPI dependency to extract just the user_id from JWT.

    This is the most commonly used dependency for RLS-protected operations.

    Usage:
        @app.get("/my-data")
        async def get_my_data(user_id: str = Depends(get_current_user_id)):
            # user_id automatically extracted and validated
            data = await tracker.get_usage_stats()  # RLS filters by user_id
            return data

    Args:
        user: Decoded JWT payload (auto-injected by get_current_user)

    Returns:
        User ID (UUID string)
    """
    return user["sub"]  # Supabase stores user ID in "sub" claim


_TRUE_VALUES = frozenset({"1", "true"})


def anonymous_allowed() -> bool:
    """True only when ALLOW_ANONYMOUS is exactly "true" or "1" (case-insensitive).

    Read per call so tests and operators can change it without a restart of the import.
    Anything else, including unset, means anonymous callers are refused on /complete.
    """
    return os.getenv("ALLOW_ANONYMOUS", "").strip().lower() in _TRUE_VALUES


def _unauthenticated() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


class OptionalAuth:
    """
    Optional authentication dependency.

    Returns user_id if a valid token is sent, None if no Authorization header is sent.
    An Authorization header that is present but not a valid, unexpired Bearer token is
    refused with 401: a bad credential is never treated as anonymous.

    Usage:
        @app.get("/chat")
        async def chat(user_id: Optional[str] = Depends(OptionalAuth())):
            ...
    """

    def __call__(self, request: Request) -> str | None:
        """Extract user_id from the Authorization header, failing closed on a bad one."""
        auth_header = request.headers.get("Authorization")

        if auth_header is None:
            return None

        scheme, _, token = auth_header.partition(" ")
        if scheme != "Bearer" or not token.strip():
            raise _unauthenticated()

        return verify_jwt_token(token.strip())["sub"]


class CompleteAuth(OptionalAuth):
    """Authentication for /complete: a valid token, or no token only if ALLOW_ANONYMOUS."""

    def __call__(self, request: Request) -> str | None:
        user_id = super().__call__(request)
        if user_id is None and not anonymous_allowed():
            raise _unauthenticated()
        return user_id


def require_admin(x_admin_key: str | None = Header(default=None)) -> None:
    """Fail-closed gate for /admin/* routes.

    ADMIN_API_KEY must be configured and the X-Admin-Key header must match it, compared in
    constant time. With no key configured every admin route answers 503, never open.
    """
    configured = os.getenv("ADMIN_API_KEY", "")
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin API is disabled: ADMIN_API_KEY is not configured",
        )
    if x_admin_key is None or not hmac.compare_digest(x_admin_key.encode(), configured.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials",
        )


# Export commonly used dependencies
__all__ = [
    "CompleteAuth",
    "OptionalAuth",
    "anonymous_allowed",
    "get_current_user",
    "get_current_user_id",
    "require_admin",
    "verify_jwt_token",
]
