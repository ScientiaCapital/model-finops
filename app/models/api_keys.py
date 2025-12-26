"""
Pydantic Models for API Key Management

Request and response schemas for API key generation, management, and usage tracking.

Security Notes:
- Raw API keys are only returned ONCE at creation time
- All other operations use key_id (UUID) or key_prefix for identification
- Keys are stored as SHA-256 hashes in the database
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# =============================================================================
# Enums
# =============================================================================

class APIKeyPermission(str, Enum):
    """Available permissions for API keys."""
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


# =============================================================================
# Create API Key
# =============================================================================

class CreateAPIKeyRequest(BaseModel):
    """Request model for creating a new API key."""
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Human-readable name for the key (e.g., 'Production App', 'Testing')"
    )
    permissions: List[APIKeyPermission] = Field(
        default=[APIKeyPermission.READ, APIKeyPermission.WRITE],
        description="List of permissions granted to this key"
    )
    rate_limit_per_minute: int = Field(
        default=60,
        ge=1,
        le=1000,
        description="Maximum requests per minute"
    )
    rate_limit_per_day: int = Field(
        default=10000,
        ge=1,
        le=1000000,
        description="Maximum requests per day"
    )
    expires_in_days: Optional[int] = Field(
        default=None,
        ge=1,
        le=365,
        description="Days until key expires (None = never expires)"
    )

    @field_validator('permissions')
    @classmethod
    def validate_permissions_not_empty(cls, v):
        if not v:
            raise ValueError("At least one permission is required")
        return v


class CreateAPIKeyResponse(BaseModel):
    """
    Response model for API key creation.

    IMPORTANT: The 'key' field contains the full API key and is ONLY
    returned at creation time. It cannot be retrieved again.
    """
    id: str = Field(..., description="Unique identifier for the key (UUID)")
    name: str = Field(..., description="Human-readable name")
    key: str = Field(..., description="The full API key - SAVE THIS NOW, cannot be retrieved later!")
    key_prefix: str = Field(..., description="First 8 characters of the key for identification")
    permissions: List[str] = Field(..., description="Granted permissions")
    rate_limit_per_minute: int
    rate_limit_per_day: int
    expires_at: Optional[datetime] = None
    created_at: datetime


# =============================================================================
# List/Get API Keys
# =============================================================================

class APIKeyInfo(BaseModel):
    """
    API key information (without the actual key).

    Used for listing and displaying key details.
    """
    id: str = Field(..., description="Unique identifier (UUID)")
    name: str = Field(..., description="Human-readable name")
    key_prefix: str = Field(..., description="First 8 characters (e.g., 'sk-abc1')")
    permissions: List[str]
    rate_limit_per_minute: int
    rate_limit_per_day: int
    is_active: bool
    last_used_at: Optional[datetime] = None
    created_at: datetime
    expires_at: Optional[datetime] = None


class ListAPIKeysResponse(BaseModel):
    """Response model for listing user's API keys."""
    keys: List[APIKeyInfo]
    total: int


# =============================================================================
# Usage Statistics
# =============================================================================

class APIKeyUsageStats(BaseModel):
    """Usage statistics for an API key."""
    api_key_id: str
    period_days: int = Field(default=30, description="Statistics period in days")

    # Totals
    total_requests: int = 0
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    total_cost_usd: float = 0.0

    # Averages
    avg_latency_ms: Optional[float] = None
    success_rate: Optional[float] = None

    # Breakdowns
    requests_by_endpoint: Dict[str, int] = Field(default_factory=dict)
    requests_by_day: List[Dict[str, Any]] = Field(default_factory=list)


class UsageRecord(BaseModel):
    """Individual usage record for an API request."""
    id: str
    api_key_id: str
    endpoint: str
    method: str
    status_code: int
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: Optional[float] = None
    created_at: datetime


class ListUsageResponse(BaseModel):
    """Response model for listing usage records."""
    records: List[UsageRecord]
    total: int
    page: int
    page_size: int


# =============================================================================
# Revoke and Rotate
# =============================================================================

class RevokeAPIKeyRequest(BaseModel):
    """Request model for revoking an API key."""
    reason: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional reason for revocation"
    )


class RevokeAPIKeyResponse(BaseModel):
    """Response model for key revocation."""
    id: str
    name: str
    revoked_at: datetime
    reason: Optional[str] = None
    message: str = "API key has been revoked and can no longer be used"


class RotateAPIKeyRequest(BaseModel):
    """Request model for rotating an API key."""
    preserve_permissions: bool = Field(
        default=True,
        description="Keep the same permissions on the new key"
    )
    preserve_rate_limits: bool = Field(
        default=True,
        description="Keep the same rate limits on the new key"
    )


class RotateAPIKeyResponse(BaseModel):
    """
    Response model for key rotation.

    The old key is immediately revoked and a new key is generated.
    """
    old_key_id: str
    old_key_revoked_at: datetime
    new_key: CreateAPIKeyResponse = Field(
        ...,
        description="The newly created key - SAVE THIS NOW!"
    )
    message: str = "Old key has been revoked. Save the new key immediately."


# =============================================================================
# Rate Limit Status
# =============================================================================

class RateLimitStatus(BaseModel):
    """Current rate limit status for an API key."""
    api_key_id: str
    is_allowed: bool
    requests_this_minute: int
    requests_today: int
    minute_limit: int
    day_limit: int
    retry_after_seconds: int = Field(
        default=0,
        description="Seconds to wait before retry (0 if allowed)"
    )

    @property
    def minute_remaining(self) -> int:
        return max(0, self.minute_limit - self.requests_this_minute)

    @property
    def day_remaining(self) -> int:
        return max(0, self.day_limit - self.requests_today)


# =============================================================================
# Update API Key
# =============================================================================

class UpdateAPIKeyRequest(BaseModel):
    """Request model for updating API key settings."""
    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="New name for the key"
    )
    permissions: Optional[List[APIKeyPermission]] = Field(
        default=None,
        description="Updated permissions list"
    )
    rate_limit_per_minute: Optional[int] = Field(
        default=None,
        ge=1,
        le=1000,
        description="Updated per-minute rate limit"
    )
    rate_limit_per_day: Optional[int] = Field(
        default=None,
        ge=1,
        le=1000000,
        description="Updated per-day rate limit"
    )

    @field_validator('permissions')
    @classmethod
    def validate_permissions_not_empty(cls, v):
        if v is not None and not v:
            raise ValueError("At least one permission is required")
        return v


class UpdateAPIKeyResponse(BaseModel):
    """Response model for API key update."""
    id: str
    name: str
    key_prefix: str
    permissions: List[str]
    rate_limit_per_minute: int
    rate_limit_per_day: int
    updated_at: datetime
    message: str = "API key settings updated successfully"


# =============================================================================
# Validation Response (for middleware)
# =============================================================================

class APIKeyValidation(BaseModel):
    """
    Internal model for API key validation result.

    Used by middleware to attach user context to requests.
    """
    key_id: str
    user_id: str
    permissions: List[str]
    rate_limit_per_minute: int
    rate_limit_per_day: int
    is_valid: bool
    error_message: Optional[str] = None
