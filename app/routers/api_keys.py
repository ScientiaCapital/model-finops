"""
API Keys Router

REST API endpoints for managing API keys.

All endpoints require JWT authentication (Bearer token) to manage keys.
The created API keys can then be used for programmatic access.

Endpoints:
- POST   /api-keys          - Create new API key
- GET    /api-keys          - List user's API keys
- GET    /api-keys/{id}     - Get specific key details
- PATCH  /api-keys/{id}     - Update key settings
- GET    /api-keys/{id}/usage - Get usage statistics
- POST   /api-keys/{id}/revoke - Revoke a key
- POST   /api-keys/{id}/rotate - Rotate a key (revoke + create new)
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from app.auth import get_current_user_id
from app.models.api_keys import (
    CreateAPIKeyRequest,
    CreateAPIKeyResponse,
    APIKeyInfo,
    ListAPIKeysResponse,
    APIKeyUsageStats,
    RevokeAPIKeyRequest,
    RevokeAPIKeyResponse,
    RotateAPIKeyRequest,
    RotateAPIKeyResponse,
    UpdateAPIKeyRequest,
    UpdateAPIKeyResponse,
)
from app.services.api_key_service import APIKeyService
from app.database.supabase_client import SupabaseClient

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api-keys",
    tags=["api-keys"],
)

# Module-level service instance (initialized by main.py)
_api_key_service: APIKeyService | None = None


def get_api_key_service() -> APIKeyService:
    """Get the API key service instance."""
    if _api_key_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API key service not initialized",
        )
    return _api_key_service


def init_api_key_service(supabase: SupabaseClient) -> None:
    """
    Initialize the API key service.

    Call this in main.py lifespan handler:
        from app.routers.api_keys import init_api_key_service
        init_api_key_service(supabase_client)
    """
    global _api_key_service
    _api_key_service = APIKeyService(supabase)
    logger.info("API key service initialized")


# =============================================================================
# Create API Key
# =============================================================================

@router.post(
    "",
    response_model=CreateAPIKeyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new API key",
    responses={
        201: {
            "description": "API key created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "name": "Production App",
                        "key": "sk-abc123def456ghi789jkl012mno345pq",
                        "key_prefix": "sk-abc1",
                        "permissions": ["read", "write"],
                        "rate_limit_per_minute": 60,
                        "rate_limit_per_day": 10000,
                        "created_at": "2024-12-26T12:00:00Z",
                    }
                }
            },
        },
    },
)
async def create_api_key(
    request: CreateAPIKeyRequest,
    user_id: str = Depends(get_current_user_id),
    service: APIKeyService = Depends(get_api_key_service),
):
    """
    Create a new API key for the authenticated user.

    **Important**: The full API key is only returned in this response.
    Save it immediately - it cannot be retrieved again.

    The key can be used in the `X-API-Key` header for programmatic access.
    """
    try:
        result = await service.create_key(user_id, request)
        logger.info(f"Created API key {result.key_prefix}... for user {user_id[:8]}...")
        return result
    except Exception as e:
        logger.error(f"Failed to create API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create API key",
        )


# =============================================================================
# List API Keys
# =============================================================================

@router.get(
    "",
    response_model=ListAPIKeysResponse,
    summary="List your API keys",
)
async def list_api_keys(
    user_id: str = Depends(get_current_user_id),
    service: APIKeyService = Depends(get_api_key_service),
):
    """
    List all API keys for the authenticated user.

    Returns key metadata (prefix, permissions, usage) but not the actual keys.
    """
    try:
        return await service.list_keys(user_id)
    except Exception as e:
        logger.error(f"Failed to list API keys: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list API keys",
        )


# =============================================================================
# Get API Key Details
# =============================================================================

@router.get(
    "/{key_id}",
    response_model=APIKeyInfo,
    summary="Get API key details",
    responses={
        404: {"description": "API key not found"},
    },
)
async def get_api_key(
    key_id: str,
    user_id: str = Depends(get_current_user_id),
    service: APIKeyService = Depends(get_api_key_service),
):
    """
    Get details for a specific API key.

    Returns key metadata but not the actual key value.
    """
    result = await service.get_key(user_id, key_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )
    return result


# =============================================================================
# Update API Key
# =============================================================================

@router.patch(
    "/{key_id}",
    response_model=UpdateAPIKeyResponse,
    summary="Update API key settings",
    responses={
        404: {"description": "API key not found"},
    },
)
async def update_api_key(
    key_id: str,
    request: UpdateAPIKeyRequest,
    user_id: str = Depends(get_current_user_id),
    service: APIKeyService = Depends(get_api_key_service),
):
    """
    Update an API key's settings (name, permissions, rate limits).

    Only the fields provided in the request will be updated.
    """
    result = await service.update_key(user_id, key_id, request)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )
    return result


# =============================================================================
# Get Usage Statistics
# =============================================================================

@router.get(
    "/{key_id}/usage",
    response_model=APIKeyUsageStats,
    summary="Get API key usage statistics",
    responses={
        404: {"description": "API key not found"},
    },
)
async def get_api_key_usage(
    key_id: str,
    days: int = Query(default=30, ge=1, le=365, description="Number of days of history"),
    user_id: str = Depends(get_current_user_id),
    service: APIKeyService = Depends(get_api_key_service),
):
    """
    Get usage statistics for an API key.

    Returns request counts, token usage, costs, and breakdowns by endpoint and day.
    """
    result = await service.get_usage_stats(user_id, key_id, days)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )
    return result


# =============================================================================
# Revoke API Key
# =============================================================================

@router.post(
    "/{key_id}/revoke",
    response_model=RevokeAPIKeyResponse,
    summary="Revoke an API key",
    responses={
        404: {"description": "API key not found"},
    },
)
async def revoke_api_key(
    key_id: str,
    request: RevokeAPIKeyRequest = RevokeAPIKeyRequest(),
    user_id: str = Depends(get_current_user_id),
    service: APIKeyService = Depends(get_api_key_service),
):
    """
    Revoke an API key immediately.

    The key will no longer be usable for authentication.
    This action cannot be undone - create a new key if needed.
    """
    result = await service.revoke_key(user_id, key_id, request.reason)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    logger.info(f"Revoked API key {key_id} for user {user_id[:8]}...")
    return result


# =============================================================================
# Rotate API Key
# =============================================================================

@router.post(
    "/{key_id}/rotate",
    response_model=RotateAPIKeyResponse,
    summary="Rotate an API key",
    responses={
        404: {"description": "API key not found"},
    },
)
async def rotate_api_key(
    key_id: str,
    request: RotateAPIKeyRequest = RotateAPIKeyRequest(),
    user_id: str = Depends(get_current_user_id),
    service: APIKeyService = Depends(get_api_key_service),
):
    """
    Rotate an API key (revoke old key and create new one).

    **Important**: The old key is immediately revoked.
    Save the new key from the response - it cannot be retrieved again.

    By default, the new key inherits permissions and rate limits from the old key.
    """
    result = await service.rotate_key(
        user_id,
        key_id,
        preserve_permissions=request.preserve_permissions,
        preserve_rate_limits=request.preserve_rate_limits,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    logger.info(f"Rotated API key {key_id} -> {result.new_key.id} for user {user_id[:8]}...")
    return result
