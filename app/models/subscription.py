"""
Subscription Tracking Models

Pydantic models for SaaS subscription tracking with billing date alerts.
Matches the database schema in supabase/migrations/20241229000001_subscriptions.sql

Features:
- Track subscription status, billing cycles, and costs
- Normalize all costs to monthly for comparison
- Alert configuration for upcoming billing
- Usage tracking for usage-based subscriptions
- Spend summaries by category
"""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, ValidationInfo, computed_field, field_validator

# =============================================================================
# Enums (matching database enums)
# =============================================================================


class SubscriptionStatus(StrEnum):
    """Subscription status states."""

    ACTIVE = "active"
    TRIAL = "trial"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    PAST_DUE = "past_due"


class BillingCycle(StrEnum):
    """Billing frequency options."""

    MONTHLY = "monthly"
    YEARLY = "yearly"
    QUARTERLY = "quarterly"
    WEEKLY = "weekly"
    ONE_TIME = "one_time"
    USAGE_BASED = "usage_based"


class ServiceCategory(StrEnum):
    """Service category for grouping subscriptions."""

    LLM_PROVIDER = "llm_provider"
    VOICE_TTS = "voice_tts"
    VOICE_STT = "voice_stt"
    INFRASTRUCTURE = "infrastructure"
    AI_MEDIA = "ai_media"
    OBSERVABILITY = "observability"
    BILLING = "billing"
    OTHER = "other"


# =============================================================================
# Base Models
# =============================================================================


class SubscriptionBase(BaseModel):
    """Base fields shared across subscription models."""

    service_name: str = Field(..., min_length=1, max_length=200)
    service_provider: str | None = Field(None, max_length=100)
    category: ServiceCategory = Field(default=ServiceCategory.OTHER)

    # Pricing
    monthly_cost: Decimal = Field(default=Decimal("0.00"), ge=0)
    original_price: Decimal | None = Field(None, ge=0)
    currency: str = Field(default="USD", max_length=3)
    billing_cycle: BillingCycle = Field(default=BillingCycle.MONTHLY)

    # Billing dates
    billing_day: int | None = Field(None, ge=1, le=31)
    next_billing_date: date | None = None
    trial_ends_at: datetime | None = None

    # Status
    status: SubscriptionStatus = Field(default=SubscriptionStatus.ACTIVE)
    auto_renew: bool = Field(default=True)

    # Alerts
    alert_days_before: int = Field(default=3, ge=0, le=30)
    alert_enabled: bool = Field(default=True)

    # Metadata
    notes: str | None = Field(None, max_length=2000)
    api_key_configured: bool = Field(default=False)
    external_subscription_id: str | None = Field(None, max_length=200)
    external_customer_id: str | None = Field(None, max_length=200)


# =============================================================================
# Request Models
# =============================================================================


class SubscriptionCreate(SubscriptionBase):
    """Request model for creating a subscription."""

    @field_validator("billing_cycle", mode="before")
    @classmethod
    def validate_billing_cycle(cls, v: object) -> object:
        if isinstance(v, str):
            return BillingCycle(v)
        return v

    @field_validator("category", mode="before")
    @classmethod
    def validate_category(cls, v: object) -> object:
        if isinstance(v, str):
            return ServiceCategory(v)
        return v

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, v: object) -> object:
        if isinstance(v, str):
            return SubscriptionStatus(v)
        return v


class SubscriptionUpdate(BaseModel):
    """Request model for updating a subscription."""

    service_name: str | None = Field(None, min_length=1, max_length=200)
    service_provider: str | None = Field(None, max_length=100)
    category: ServiceCategory | None = None

    monthly_cost: Decimal | None = Field(None, ge=0)
    original_price: Decimal | None = Field(None, ge=0)
    currency: str | None = Field(None, max_length=3)
    billing_cycle: BillingCycle | None = None

    billing_day: int | None = Field(None, ge=1, le=31)
    next_billing_date: date | None = None
    trial_ends_at: datetime | None = None

    status: SubscriptionStatus | None = None
    auto_renew: bool | None = None

    alert_days_before: int | None = Field(None, ge=0, le=30)
    alert_enabled: bool | None = None

    notes: str | None = Field(None, max_length=2000)
    api_key_configured: bool | None = None
    external_subscription_id: str | None = Field(None, max_length=200)
    external_customer_id: str | None = Field(None, max_length=200)


# =============================================================================
# Response Models
# =============================================================================


class SubscriptionResponse(BaseModel):
    """Response model for a subscription."""

    id: str
    user_id: str

    # Service identification
    service_name: str
    service_provider: str | None = None
    category: str

    # Pricing
    monthly_cost: Decimal
    original_price: Decimal | None = None
    currency: str
    billing_cycle: str

    # Billing dates
    billing_day: int | None = None
    next_billing_date: date | None = None
    trial_ends_at: datetime | None = None

    # Status
    status: str
    auto_renew: bool

    # Alerts
    alert_days_before: int
    alert_enabled: bool
    last_alert_sent_at: datetime | None = None

    # Metadata
    notes: str | None = None
    api_key_configured: bool
    external_subscription_id: str | None = None
    external_customer_id: str | None = None

    # Audit
    created_at: datetime
    updated_at: datetime | None = None

    @computed_field
    @property
    def yearly_cost(self) -> Decimal:
        """Calculate yearly cost from monthly."""
        return self.monthly_cost * 12

    @computed_field
    @property
    def is_trial(self) -> bool:
        """Check if subscription is in trial period."""
        return self.status == SubscriptionStatus.TRIAL.value


class SubscriptionListResponse(BaseModel):
    """Response model for list of subscriptions."""

    subscriptions: list[SubscriptionResponse]
    total: int

    @computed_field
    @property
    def total_monthly_cost(self) -> Decimal:
        """Sum of all monthly costs."""
        return sum(s.monthly_cost for s in self.subscriptions)


# =============================================================================
# Usage Models (for usage-based billing tracking)
# =============================================================================


class SubscriptionUsageCreate(BaseModel):
    """Request model for recording usage."""

    period_start: date
    period_end: date
    usage_amount: Decimal = Field(..., ge=0)
    usage_unit: str = Field(default="tokens", max_length=50)
    cost_usd: Decimal = Field(default=Decimal("0.00"), ge=0)
    breakdown: dict[str, Any] | None = None

    @field_validator("period_end")
    @classmethod
    def validate_period_end(cls, v: date, info: ValidationInfo) -> date:
        if "period_start" in info.data and v < info.data["period_start"]:
            raise ValueError("period_end must be after period_start")
        return v


class SubscriptionUsageResponse(BaseModel):
    """Response model for usage record."""

    id: str
    subscription_id: str
    user_id: str

    period_start: date
    period_end: date

    usage_amount: Decimal
    usage_unit: str
    cost_usd: Decimal

    breakdown: dict[str, Any] | None = None
    created_at: datetime


class UsageSummaryResponse(BaseModel):
    """Summary of usage across a period."""

    subscription_id: str
    service_name: str
    total_usage: Decimal
    total_cost: Decimal
    usage_unit: str
    period_count: int


# =============================================================================
# Alert Models
# =============================================================================


class SubscriptionAlertCreate(BaseModel):
    """Request model for creating an alert record."""

    alert_type: str = Field(..., max_length=50)
    message: str | None = Field(None, max_length=500)
    channels: list[str] = Field(default_factory=list)
    billing_date: date | None = None
    amount: Decimal | None = None


class SubscriptionAlertResponse(BaseModel):
    """Response model for alert record."""

    id: str
    subscription_id: str
    user_id: str

    alert_type: str
    message: str | None = None

    sent_at: datetime
    channels: list[str]
    delivery_status: str

    billing_date: date | None = None
    amount: Decimal | None = None


class UpcomingBillingAlert(BaseModel):
    """Upcoming billing alert from the database function."""

    subscription_id: str
    user_id: str
    service_name: str
    monthly_cost: Decimal
    next_billing_date: date
    days_until_billing: int
    alert_days_before: int

    @computed_field
    @property
    def urgency(self) -> str:
        """Determine urgency level based on days until billing."""
        if self.days_until_billing <= 1:
            return "critical"
        elif self.days_until_billing <= 3:
            return "high"
        elif self.days_until_billing <= 7:
            return "medium"
        return "low"


class UpcomingBillingListResponse(BaseModel):
    """Response model for list of upcoming billing alerts."""

    alerts: list[UpcomingBillingAlert]
    total_upcoming_cost: Decimal

    @computed_field
    @property
    def alert_count(self) -> int:
        """Number of upcoming alerts."""
        return len(self.alerts)


# =============================================================================
# Spend Summary Models
# =============================================================================


class CategorySpend(BaseModel):
    """Spend breakdown by category."""

    category: str
    monthly_cost: Decimal
    subscription_count: int


class SpendSummary(BaseModel):
    """Monthly spend summary from the database function."""

    total_monthly_cost: Decimal
    total_yearly_cost: Decimal
    active_subscriptions: int
    by_category: dict[str, Decimal] = Field(default_factory=dict)

    @computed_field
    @property
    def average_per_subscription(self) -> Decimal:
        """Average monthly cost per subscription."""
        if self.active_subscriptions == 0:
            return Decimal("0.00")
        return self.total_monthly_cost / self.active_subscriptions

    @computed_field
    @property
    def top_category(self) -> str | None:
        """Category with highest spend."""
        if not self.by_category:
            return None
        return max(self.by_category, key=self.by_category.get)


# =============================================================================
# Import Models
# =============================================================================


class SubscriptionImportRow(BaseModel):
    """Single row from CSV import."""

    service_name: str
    monthly_cost: Decimal
    billing_cycle: str | None = "monthly"
    category: str | None = "other"
    billing_day: int | None = None
    notes: str | None = None


class SubscriptionImportRequest(BaseModel):
    """Request model for bulk import."""

    subscriptions: list[SubscriptionImportRow]
    skip_duplicates: bool = Field(default=True)


class SubscriptionImportResult(BaseModel):
    """Result of import operation."""

    imported: int
    skipped: int
    errors: list[str]
    subscriptions: list[SubscriptionResponse]


# =============================================================================
# Filter Models
# =============================================================================


class SubscriptionFilters(BaseModel):
    """Filter options for listing subscriptions."""

    category: ServiceCategory | None = None
    status: SubscriptionStatus | None = None
    min_cost: Decimal | None = None
    max_cost: Decimal | None = None
    billing_cycle: BillingCycle | None = None
    search: str | None = None
