"""
API Key Service - Secure key management for the AI Cost Optimizer

This service handles:
- Cryptographically secure key generation (sk-xxx format)
- SHA-256 hashing for storage (never store plaintext)
- Key validation and rate limit checking
- Usage tracking and analytics

Security Notes:
- Keys are generated using secrets.token_urlsafe (cryptographically secure)
- Only SHA-256 hashes are stored in the database
- The full key is returned ONCE at creation - it cannot be retrieved later
"""

import secrets
import hashlib
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta, timezone
from app.database.supabase_client import SupabaseClient
from app.models.api_keys import (
    CreateAPIKeyRequest,
    CreateAPIKeyResponse,
    APIKeyInfo,
    ListAPIKeysResponse,
    APIKeyUsageStats,
    RevokeAPIKeyResponse,
    RotateAPIKeyResponse,
    RateLimitStatus,
    UpdateAPIKeyRequest,
    UpdateAPIKeyResponse,
    APIKeyValidation,
)

logger = logging.getLogger(__name__)


class APIKeyService:
    """
    Service for managing API keys.

    All operations are user-scoped via RLS policies in Supabase.
    Admin operations use the service key to bypass RLS when needed.
    """

    # Key format: sk-{32 random chars} = 35 chars total
    KEY_PREFIX = "sk-"
    KEY_RANDOM_BYTES = 24  # Produces 32 urlsafe chars

    def __init__(self, supabase: SupabaseClient):
        """
        Initialize the API key service.

        Args:
            supabase: Configured Supabase client with user context
        """
        self.db = supabase

    # =========================================================================
    # Key Generation Helpers
    # =========================================================================

    def _generate_key(self) -> Tuple[str, str, str]:
        """
        Generate a new API key.

        Returns:
            Tuple of (full_key, key_prefix, key_hash)
        """
        # Generate cryptographically secure random bytes
        random_part = secrets.token_urlsafe(self.KEY_RANDOM_BYTES)
        full_key = f"{self.KEY_PREFIX}{random_part}"

        # Create display prefix (first 8 chars: sk-XXXX)
        key_prefix = full_key[:8]

        # Hash for storage
        key_hash = self._hash_key(full_key)

        return full_key, key_prefix, key_hash

    def _hash_key(self, key: str) -> str:
        """
        Create SHA-256 hash of an API key.

        Args:
            key: The full API key

        Returns:
            Hex-encoded SHA-256 hash
        """
        return hashlib.sha256(key.encode()).hexdigest()

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    async def create_key(
        self,
        user_id: str,
        request: CreateAPIKeyRequest
    ) -> CreateAPIKeyResponse:
        """
        Create a new API key for a user.

        Args:
            user_id: The user creating the key
            request: Key creation parameters

        Returns:
            The created key (including the full key - only returned once!)
        """
        # Generate secure key
        full_key, key_prefix, key_hash = self._generate_key()

        # Calculate expiration if specified
        expires_at = None
        if request.expires_in_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=request.expires_in_days)

        # Prepare data for insert
        data = {
            "user_id": user_id,
            "name": request.name,
            "key_prefix": key_prefix,
            "key_hash": key_hash,
            "permissions": [p.value for p in request.permissions],
            "rate_limit_per_minute": request.rate_limit_per_minute,
            "rate_limit_per_day": request.rate_limit_per_day,
            "is_active": True,
        }

        if expires_at:
            data["expires_at"] = expires_at.isoformat()

        # Insert into database (RLS ensures user_id matches)
        result = await self.db.insert("api_keys", data, use_admin=True)

        logger.info(f"Created API key {key_prefix}... for user {user_id}")

        return CreateAPIKeyResponse(
            id=result["id"],
            name=result["name"],
            key=full_key,  # Only time this is returned!
            key_prefix=key_prefix,
            permissions=result["permissions"],
            rate_limit_per_minute=result["rate_limit_per_minute"],
            rate_limit_per_day=result["rate_limit_per_day"],
            expires_at=expires_at,
            created_at=datetime.fromisoformat(result["created_at"].replace("Z", "+00:00")),
        )

    async def list_keys(self, user_id: str) -> ListAPIKeysResponse:
        """
        List all API keys for a user.

        Args:
            user_id: The user whose keys to list

        Returns:
            List of API key info (without actual keys)
        """
        results = await self.db.select(
            "api_keys",
            columns="*",
            filters={"user_id": user_id},
            order_by="-created_at",
            use_admin=True,
        )

        keys = []
        for row in results:
            keys.append(APIKeyInfo(
                id=row["id"],
                name=row["name"],
                key_prefix=row["key_prefix"],
                permissions=row["permissions"],
                rate_limit_per_minute=row["rate_limit_per_minute"],
                rate_limit_per_day=row["rate_limit_per_day"],
                is_active=row["is_active"],
                last_used_at=datetime.fromisoformat(row["last_used_at"].replace("Z", "+00:00")) if row.get("last_used_at") else None,
                created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
                expires_at=datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00")) if row.get("expires_at") else None,
            ))

        return ListAPIKeysResponse(keys=keys, total=len(keys))

    async def get_key(self, user_id: str, key_id: str) -> Optional[APIKeyInfo]:
        """
        Get a specific API key by ID.

        Args:
            user_id: The key owner
            key_id: The key's UUID

        Returns:
            API key info or None if not found
        """
        results = await self.db.select(
            "api_keys",
            columns="*",
            filters={"id": key_id, "user_id": user_id},
            use_admin=True,
        )

        if not results:
            return None

        row = results[0]
        return APIKeyInfo(
            id=row["id"],
            name=row["name"],
            key_prefix=row["key_prefix"],
            permissions=row["permissions"],
            rate_limit_per_minute=row["rate_limit_per_minute"],
            rate_limit_per_day=row["rate_limit_per_day"],
            is_active=row["is_active"],
            last_used_at=datetime.fromisoformat(row["last_used_at"].replace("Z", "+00:00")) if row.get("last_used_at") else None,
            created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
            expires_at=datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00")) if row.get("expires_at") else None,
        )

    async def update_key(
        self,
        user_id: str,
        key_id: str,
        request: UpdateAPIKeyRequest
    ) -> Optional[UpdateAPIKeyResponse]:
        """
        Update API key settings.

        Args:
            user_id: The key owner
            key_id: The key's UUID
            request: Fields to update

        Returns:
            Updated key info or None if not found
        """
        # Build update data from non-None fields
        data = {}
        if request.name is not None:
            data["name"] = request.name
        if request.permissions is not None:
            data["permissions"] = [p.value for p in request.permissions]
        if request.rate_limit_per_minute is not None:
            data["rate_limit_per_minute"] = request.rate_limit_per_minute
        if request.rate_limit_per_day is not None:
            data["rate_limit_per_day"] = request.rate_limit_per_day

        if not data:
            # Nothing to update, return current state
            key = await self.get_key(user_id, key_id)
            if key:
                return UpdateAPIKeyResponse(
                    id=key.id,
                    name=key.name,
                    key_prefix=key.key_prefix,
                    permissions=key.permissions,
                    rate_limit_per_minute=key.rate_limit_per_minute,
                    rate_limit_per_day=key.rate_limit_per_day,
                    updated_at=key.created_at,  # No change
                    message="No changes made",
                )
            return None

        results = await self.db.update(
            "api_keys",
            data=data,
            filters={"id": key_id, "user_id": user_id},
            use_admin=True,
        )

        if not results:
            return None

        row = results[0]
        logger.info(f"Updated API key {key_id} for user {user_id}")

        return UpdateAPIKeyResponse(
            id=row["id"],
            name=row["name"],
            key_prefix=row["key_prefix"],
            permissions=row["permissions"],
            rate_limit_per_minute=row["rate_limit_per_minute"],
            rate_limit_per_day=row["rate_limit_per_day"],
            updated_at=datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00")),
        )

    async def revoke_key(
        self,
        user_id: str,
        key_id: str,
        reason: Optional[str] = None
    ) -> Optional[RevokeAPIKeyResponse]:
        """
        Revoke an API key (immediate invalidation).

        Args:
            user_id: The key owner
            key_id: The key's UUID
            reason: Optional revocation reason

        Returns:
            Revocation confirmation or None if not found
        """
        revoked_at = datetime.now(timezone.utc)

        results = await self.db.update(
            "api_keys",
            data={
                "is_active": False,
                "revoked_at": revoked_at.isoformat(),
                "revoked_reason": reason,
            },
            filters={"id": key_id, "user_id": user_id},
            use_admin=True,
        )

        if not results:
            return None

        row = results[0]
        logger.info(f"Revoked API key {key_id} for user {user_id}: {reason}")

        return RevokeAPIKeyResponse(
            id=row["id"],
            name=row["name"],
            revoked_at=revoked_at,
            reason=reason,
        )

    async def rotate_key(
        self,
        user_id: str,
        key_id: str,
        preserve_permissions: bool = True,
        preserve_rate_limits: bool = True
    ) -> Optional[RotateAPIKeyResponse]:
        """
        Rotate an API key (revoke old, create new).

        Args:
            user_id: The key owner
            key_id: The key's UUID
            preserve_permissions: Copy permissions to new key
            preserve_rate_limits: Copy rate limits to new key

        Returns:
            New key and old key revocation info
        """
        # Get current key
        current_key = await self.get_key(user_id, key_id)
        if not current_key:
            return None

        # Revoke old key
        revoke_result = await self.revoke_key(user_id, key_id, reason="Rotated")
        if not revoke_result:
            return None

        # Create new key with same/default settings
        from app.models.api_keys import APIKeyPermission

        create_request = CreateAPIKeyRequest(
            name=f"{current_key.name} (rotated)",
            permissions=[APIKeyPermission(p) for p in current_key.permissions] if preserve_permissions else [APIKeyPermission.READ, APIKeyPermission.WRITE],
            rate_limit_per_minute=current_key.rate_limit_per_minute if preserve_rate_limits else 60,
            rate_limit_per_day=current_key.rate_limit_per_day if preserve_rate_limits else 10000,
        )

        new_key = await self.create_key(user_id, create_request)

        logger.info(f"Rotated API key {key_id} -> {new_key.id} for user {user_id}")

        return RotateAPIKeyResponse(
            old_key_id=key_id,
            old_key_revoked_at=revoke_result.revoked_at,
            new_key=new_key,
        )

    # =========================================================================
    # Validation and Rate Limiting
    # =========================================================================

    async def validate_key(self, api_key: str) -> APIKeyValidation:
        """
        Validate an API key and return user context.

        This is called by the authentication middleware on every request.

        Args:
            api_key: The full API key from the request header

        Returns:
            Validation result with user context
        """
        # Hash the provided key
        key_hash = self._hash_key(api_key)

        # Call the database function
        try:
            result = await self._call_validate_function(key_hash)

            if not result or not result.get("is_valid"):
                return APIKeyValidation(
                    key_id="",
                    user_id="",
                    permissions=[],
                    rate_limit_per_minute=0,
                    rate_limit_per_day=0,
                    is_valid=False,
                    error_message=result.get("error_message", "Invalid API key") if result else "Invalid API key",
                )

            return APIKeyValidation(
                key_id=result["key_id"],
                user_id=result["user_id"],
                permissions=result["permissions"],
                rate_limit_per_minute=result["rate_limit_per_minute"],
                rate_limit_per_day=result["rate_limit_per_day"],
                is_valid=True,
            )

        except Exception as e:
            logger.error(f"Key validation error: {e}")
            return APIKeyValidation(
                key_id="",
                user_id="",
                permissions=[],
                rate_limit_per_minute=0,
                rate_limit_per_day=0,
                is_valid=False,
                error_message="Key validation failed",
            )

    async def _call_validate_function(self, key_hash: str) -> Optional[Dict[str, Any]]:
        """Call the database validate_api_key function."""
        # Use RPC call to the database function
        client = self.db.admin_client or self.db.client
        response = client.rpc("validate_api_key", {"p_key_hash": key_hash}).execute()

        if response.data:
            return response.data[0] if isinstance(response.data, list) else response.data
        return None

    async def check_rate_limit(self, key_id: str) -> RateLimitStatus:
        """
        Check if a key is within rate limits.

        Args:
            key_id: The API key's UUID

        Returns:
            Rate limit status with current counts
        """
        try:
            client = self.db.admin_client or self.db.client
            response = client.rpc("check_rate_limit", {"p_api_key_id": key_id}).execute()

            if response.data:
                data = response.data[0] if isinstance(response.data, list) else response.data
                return RateLimitStatus(
                    api_key_id=key_id,
                    is_allowed=data["is_allowed"],
                    requests_this_minute=data["requests_this_minute"],
                    requests_today=data["requests_today"],
                    minute_limit=data["minute_limit"],
                    day_limit=data["day_limit"],
                    retry_after_seconds=data["retry_after_seconds"],
                )

            # Fallback if function returns nothing
            return RateLimitStatus(
                api_key_id=key_id,
                is_allowed=False,
                requests_this_minute=0,
                requests_today=0,
                minute_limit=0,
                day_limit=0,
                retry_after_seconds=60,
            )

        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            # Fail closed - deny if we can't check
            return RateLimitStatus(
                api_key_id=key_id,
                is_allowed=False,
                requests_this_minute=0,
                requests_today=0,
                minute_limit=0,
                day_limit=0,
                retry_after_seconds=60,
            )

    # =========================================================================
    # Usage Tracking
    # =========================================================================

    async def record_usage(
        self,
        key_id: str,
        user_id: str,
        endpoint: str,
        method: str,
        status_code: int,
        tokens_in: int = 0,
        tokens_out: int = 0,
        cost_usd: float = 0.0,
        latency_ms: Optional[float] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> str:
        """
        Record API key usage for a request.

        Args:
            key_id: The API key's UUID
            user_id: The key owner
            endpoint: The API endpoint called
            method: HTTP method (GET, POST, etc.)
            status_code: HTTP response status code
            tokens_in: Input tokens used
            tokens_out: Output tokens used
            cost_usd: Cost in USD
            latency_ms: Response latency in milliseconds
            ip_address: Client IP address
            user_agent: Client user agent
            request_id: Unique request identifier

        Returns:
            The usage record ID
        """
        try:
            client = self.db.admin_client or self.db.client
            response = client.rpc("record_api_key_usage", {
                "p_api_key_id": key_id,
                "p_user_id": user_id,
                "p_endpoint": endpoint,
                "p_method": method,
                "p_status_code": status_code,
                "p_tokens_in": tokens_in,
                "p_tokens_out": tokens_out,
                "p_cost_usd": cost_usd,
                "p_latency_ms": latency_ms,
                "p_ip_address": ip_address,
                "p_user_agent": user_agent,
                "p_request_id": request_id,
            }).execute()

            return response.data if response.data else ""

        except Exception as e:
            logger.error(f"Usage recording error: {e}")
            return ""

    async def get_usage_stats(
        self,
        user_id: str,
        key_id: str,
        days: int = 30
    ) -> Optional[APIKeyUsageStats]:
        """
        Get usage statistics for an API key.

        Args:
            user_id: The key owner (for authorization)
            key_id: The API key's UUID
            days: Number of days of history

        Returns:
            Usage statistics or None if key not found
        """
        # Verify key belongs to user
        key = await self.get_key(user_id, key_id)
        if not key:
            return None

        try:
            client = self.db.admin_client or self.db.client
            response = client.rpc("get_api_key_stats", {
                "p_api_key_id": key_id,
                "p_days": days,
            }).execute()

            if response.data:
                data = response.data[0] if isinstance(response.data, list) else response.data
                return APIKeyUsageStats(
                    api_key_id=key_id,
                    period_days=days,
                    total_requests=data.get("total_requests", 0),
                    total_tokens_in=data.get("total_tokens_in", 0),
                    total_tokens_out=data.get("total_tokens_out", 0),
                    total_cost_usd=data.get("total_cost_usd", 0.0),
                    avg_latency_ms=data.get("avg_latency_ms"),
                    success_rate=data.get("success_rate"),
                    requests_by_endpoint=data.get("requests_by_endpoint") or {},
                    requests_by_day=data.get("requests_by_day") or [],
                )

            # No usage data
            return APIKeyUsageStats(api_key_id=key_id, period_days=days)

        except Exception as e:
            logger.error(f"Usage stats error: {e}")
            return APIKeyUsageStats(api_key_id=key_id, period_days=days)


# =============================================================================
# Factory function for easy instantiation
# =============================================================================

def create_api_key_service(supabase: SupabaseClient) -> APIKeyService:
    """
    Create an API key service instance.

    Args:
        supabase: Configured Supabase client

    Returns:
        Configured APIKeyService instance
    """
    return APIKeyService(supabase)
