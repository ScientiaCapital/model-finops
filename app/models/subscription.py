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

from pydantic import BaseModel, Field, field_validator, computed_field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal
from enum import Enum


# =============================================================================
# Enums (matching database enums)
# =============================================================================

class SubscriptionStatus(str, Enum):
    """Subscription status states."""
    ACTIVE = "active"
    TRIAL = "trial"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    PAST_DUE = "past_due"


class BillingCycle(str, Enum):
    """Billing frequency options."""
    MONTHLY = "monthly"
    YEARLY = "yearly"
    QUARTERLY = "quarterly"
    WEEKLY = "weekly"
    ONE_TIME = "one_time"
    USAGE_BASED = "usage_based"


class ServiceCategory(str, Enum):
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
    service_provider: Optional[str] = Field(None, max_length=100)
    category: ServiceCategory = Field(default=ServiceCategory.OTHER)

    # Pricing
    monthly_cost: Decimal = Field(default=Decimal("0.00"), ge=0)
    original_price: Optional[Decimal] = Field(None, ge=0)
    currency: str = Field(default="USD", max_length=3)
    billing_cycle: BillingCycle = Field(default=BillingCycle.MONTHLY)

    # Billing dates
    billing_day: Optional[int] = Field(None, ge=1, le=31)
    next_billing_date: Optional[date] = None
    trial_ends_at: Optional[datetime] = None

    # Status
    status: SubscriptionStatus = Field(default=SubscriptionStatus.ACTIVE)
    auto_renew: bool = Field(default=True)

    # Alerts
    alert_days_before: int = Field(default=3, ge=0, le=30)
    alert_enabled: bool = Field(default=True)

    # Metadata
    notes: Optional[str] = Field(None, max_length=2000)
    api_key_configured: bool = Field(default=False)
    external_subscription_id: Optional[str] = Field(None, max_length=200)
    external_customer_id: Optional[str] = Field(None, max_length=200)


# =============================================================================
# Request Models
# =============================================================================

class SubscriptionCreate(SubscriptionBase):
    """Request model for creating a subscription."""

    @field_validator('billing_cycle', mode='before')
    @classmethod
    def validate_billing_cycle(cls, v):
        if isinstance(v, str):
            return BillingCycle(v)
        return v

    @field_validator('category', mode='before')
    @classmethod
    def validate_category(cls, v):
        if isinstance(v, str):
            return ServiceCategory(v)
        return v

    @field_validator('status', mode='before')
    @classmethod
    def validate_status(cls, v):
        if isinstance(v, str):
            return SubscriptionStatus(v)
        return v


class SubscriptionUpdate(BaseModel):
    """Request model for updating a subscription."""
    service_name: Optional[str] = Field(None, min_length=1, max_length=200)
    service_provider: Optional[str] = Field(None, max_length=100)
    category: Optional[ServiceCategory] = None

    monthly_cost: Optional[Decimal] = Field(None, ge=0)
    original_price: Optional[Decimal] = Field(None, ge=0)
    currency: Optional[str] = Field(None, max_length=3)
    billing_cycle: Optional[BillingCycle] = None

    billing_day: Optional[int] = Field(None, ge=1, le=31)
    next_billing_date: Optional[date] = None
    trial_ends_at: Optional[datetime] = None

    status: Optional[SubscriptionStatus] = None
    auto_renew: Optional[bool] = None

    alert_days_before: Optional[int] = Field(None, ge=0, le=30)
    alert_enabled: Optional[bool] = None

    notes: Optional[str] = Field(None, max_length=2000)
    api_key_configured: Optional[bool] = None
    external_subscription_id: Optional[str] = Field(None, max_length=200)
    external_customer_id: Optional[str] = Field(None, max_length=200)


# =============================================================================
# Response Models
# =============================================================================

class SubscriptionResponse(BaseModel):
    """Response model for a subscription."""
    id: str
    user_id: str

    # Service identification
    service_name: str
    service_provider: Optional[str] = None
    category: str

    # Pricing
    monthly_cost: Decimal
    original_price: Optional[Decimal] = None
    currency: str
    billing_cycle: str

    # Billing dates
    billing_day: Optional[int] = None
    next_billing_date: Optional[date] = None
    trial_ends_at: Optional[datetime] = None

    # Status
    status: str
    auto_renew: bool

    # Alerts
    alert_days_before: int
    alert_enabled: bool
    last_alert_sent_at: Optional[datetime] = None

    # Metadata
    notes: Optional[str] = None
    api_key_configured: bool
    external_subscription_id: Optional[str] = None
    external_customer_id: Optional[str] = None

    # Audit
    created_at: datetime
    updated_at: Optional[datetime] = None

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
    subscriptions: List[SubscriptionResponse]
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
    breakdown: Optional[Dict[str, Any]] = None

    @field_validator('period_end')
    @classmethod
    def validate_period_end(cls, v, info):
        if 'period_start' in info.data and v < info.data['period_start']:
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

    breakdown: Optional[Dict[str, Any]] = None
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
    message: Optional[str] = Field(None, max_length=500)
    channels: List[str] = Field(default_factory=list)
    billing_date: Optional[date] = None
    amount: Optional[Decimal] = None


class SubscriptionAlertResponse(BaseModel):
    """Response model for alert record."""
    id: str
    subscription_id: str
    user_id: str

    alert_type: str
    message: Optional[str] = None

    sent_at: datetime
    channels: List[str]
    delivery_status: str

    billing_date: Optional[date] = None
    amount: Optional[Decimal] = None


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
    alerts: List[UpcomingBillingAlert]
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
    by_category: Dict[str, Decimal] = Field(default_factory=dict)

    @computed_field
    @property
    def average_per_subscription(self) -> Decimal:
        """Average monthly cost per subscription."""
        if self.active_subscriptions == 0:
            return Decimal("0.00")
        return self.total_monthly_cost / self.active_subscriptions

    @computed_field
    @property
    def top_category(self) -> Optional[str]:
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
    billing_cycle: Optional[str] = "monthly"
    category: Optional[str] = "other"
    billing_day: Optional[int] = None
    notes: Optional[str] = None


class SubscriptionImportRequest(BaseModel):
    """Request model for bulk import."""
    subscriptions: List[SubscriptionImportRow]
    skip_duplicates: bool = Field(default=True)


class SubscriptionImportResult(BaseModel):
    """Result of import operation."""
    imported: int
    skipped: int
    errors: List[str]
    subscriptions: List[SubscriptionResponse]


# =============================================================================
# Filter Models
# =============================================================================

class SubscriptionFilters(BaseModel):
    """Filter options for listing subscriptions."""
    category: Optional[ServiceCategory] = None
    status: Optional[SubscriptionStatus] = None
    min_cost: Optional[Decimal] = None
    max_cost: Optional[Decimal] = None
    billing_cycle: Optional[BillingCycle] = None
    search: Optional[str] = None
