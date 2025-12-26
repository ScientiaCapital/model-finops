"""
Billing Service Layer

Orchestrates billing operations between Stripe and Supabase database.
Handles subscription management, usage tracking, and quota enforcement.

Usage:
    from app.services.billing_service import BillingService
    from app.billing import StripeClient
    from app.database.supabase_client import SupabaseClient

    stripe_client = StripeClient()
    supabase_client = SupabaseClient()
    billing_service = BillingService(stripe_client, supabase_client)

    # Get or create customer
    customer = await billing_service.get_or_create_customer(user_id, email)

    # Check quota before API call
    quota = await billing_service.check_quota(user_id)
    if not quota.has_quota:
        raise HTTPException(429, "Quota exceeded")

    # Record usage after API call
    await billing_service.record_usage(user_id, tokens=150, cost_cents=5)
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from app.billing.stripe_client import (
    StripeClient,
    StripeCustomer,
    StripeSubscription,
    StripeCheckoutSession,
    StripeBillingPortalSession,
    StripeInvoice,
)
from app.database.supabase_client import SupabaseClient

logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic Models
# =============================================================================

class CustomerInfo(BaseModel):
    """Customer information combining Supabase and Stripe data."""
    id: str
    user_id: str
    stripe_customer_id: str
    email: str
    name: Optional[str] = None
    created_at: datetime


class SubscriptionInfo(BaseModel):
    """Subscription information for a user."""
    id: str
    user_id: str
    stripe_subscription_id: str
    tier: str
    status: str
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool = False
    features: Dict[str, Any] = Field(default_factory=dict)


class UsageInfo(BaseModel):
    """Current period usage information."""
    user_id: str
    period_start: datetime
    period_end: datetime
    tokens_used: int
    tokens_limit: int
    tokens_remaining: int
    usage_percentage: float
    requests_count: int
    requests_limit: Optional[int] = None
    estimated_cost_cents: int
    cache_hits: int
    cache_misses: int


class QuotaStatus(BaseModel):
    """Quota check result."""
    has_quota: bool
    tokens_used: int
    tokens_limit: int
    tokens_remaining: int
    usage_percentage: float
    tier: str
    period_ends_at: datetime
    upgrade_url: Optional[str] = None


class BillingSummary(BaseModel):
    """Comprehensive billing summary for dashboard display."""
    customer_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    subscription: Optional[SubscriptionInfo] = None
    usage: UsageInfo
    tier: str
    features: Dict[str, Any] = Field(default_factory=dict)
    next_invoice_date: Optional[datetime] = None
    amount_due_cents: Optional[int] = None


class TierInfo(BaseModel):
    """Subscription tier information."""
    tier: str
    monthly_token_limit: int
    monthly_request_limit: Optional[int] = None
    rate_limit_per_minute: int
    rate_limit_per_day: int
    features: Dict[str, Any] = Field(default_factory=dict)
    price_usd_monthly: Optional[float] = None
    stripe_price_id: Optional[str] = None


# =============================================================================
# Billing Service
# =============================================================================

class BillingService:
    """
    Service layer for billing operations.

    Coordinates between Stripe (payments) and Supabase (data storage).
    """

    def __init__(
        self,
        stripe_client: StripeClient,
        supabase_client: SupabaseClient,
    ):
        """
        Initialize billing service.

        Args:
            stripe_client: Configured Stripe client
            supabase_client: Configured Supabase client
        """
        self.stripe = stripe_client
        self.db = supabase_client
        logger.info("Billing service initialized")

    # =========================================================================
    # Customer Management
    # =========================================================================

    async def get_or_create_customer(
        self,
        user_id: str,
        email: str,
        name: Optional[str] = None,
    ) -> CustomerInfo:
        """
        Get or create a customer record linked to Supabase user.

        Args:
            user_id: Supabase auth user ID
            email: User's email address
            name: User's display name

        Returns:
            Customer information
        """
        # Check for existing customer
        existing = await self.db.execute_query(
            "customers",
            "select",
            filters={"user_id": user_id},
        )

        if existing:
            return CustomerInfo(
                id=existing[0]["id"],
                user_id=existing[0]["user_id"],
                stripe_customer_id=existing[0]["stripe_customer_id"],
                email=existing[0]["email"],
                name=existing[0].get("name"),
                created_at=datetime.fromisoformat(existing[0]["created_at"].replace("Z", "+00:00")),
            )

        # Create Stripe customer
        stripe_customer = await self.stripe.create_customer(
            email=email,
            name=name,
            metadata={"supabase_user_id": user_id},
        )

        # Store in Supabase
        result = await self.db.execute_query(
            "customers",
            "insert",
            data={
                "user_id": user_id,
                "stripe_customer_id": stripe_customer.id,
                "email": email,
                "name": name,
            },
        )

        logger.info(f"Created customer for user {user_id[:8]}...: {stripe_customer.id}")

        return CustomerInfo(
            id=result[0]["id"],
            user_id=user_id,
            stripe_customer_id=stripe_customer.id,
            email=email,
            name=name,
            created_at=datetime.fromisoformat(result[0]["created_at"].replace("Z", "+00:00")),
        )

    async def get_customer(self, user_id: str) -> Optional[CustomerInfo]:
        """
        Get customer record by user ID.

        Args:
            user_id: Supabase auth user ID

        Returns:
            Customer info or None if not found
        """
        result = await self.db.execute_query(
            "customers",
            "select",
            filters={"user_id": user_id},
        )

        if not result:
            return None

        return CustomerInfo(
            id=result[0]["id"],
            user_id=result[0]["user_id"],
            stripe_customer_id=result[0]["stripe_customer_id"],
            email=result[0]["email"],
            name=result[0].get("name"),
            created_at=datetime.fromisoformat(result[0]["created_at"].replace("Z", "+00:00")),
        )

    # =========================================================================
    # Checkout & Portal Sessions
    # =========================================================================

    async def create_checkout_session(
        self,
        user_id: str,
        email: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        trial_days: Optional[int] = None,
    ) -> StripeCheckoutSession:
        """
        Create a Stripe Checkout session for subscription purchase.

        Args:
            user_id: Supabase auth user ID
            email: User's email
            price_id: Stripe price ID for the plan
            success_url: Redirect URL after successful payment
            cancel_url: Redirect URL if user cancels
            trial_days: Optional trial period

        Returns:
            Checkout session with redirect URL
        """
        # Get or create customer
        customer = await self.get_or_create_customer(user_id, email)

        # Create checkout session
        session = await self.stripe.create_checkout_session(
            price_id=price_id,
            success_url=success_url,
            cancel_url=cancel_url,
            customer_id=customer.stripe_customer_id,
            metadata={"supabase_user_id": user_id},
            trial_days=trial_days,
        )

        logger.info(f"Created checkout session for user {user_id[:8]}...: {session.id}")
        return session

    async def create_portal_session(
        self,
        user_id: str,
        return_url: str,
    ) -> StripeBillingPortalSession:
        """
        Create a billing portal session for self-service management.

        Args:
            user_id: Supabase auth user ID
            return_url: URL to return to after portal session

        Returns:
            Portal session with redirect URL

        Raises:
            ValueError: If no customer exists for user
        """
        customer = await self.get_customer(user_id)
        if not customer:
            raise ValueError(f"No customer found for user {user_id}")

        session = await self.stripe.create_portal_session(
            customer_id=customer.stripe_customer_id,
            return_url=return_url,
        )

        logger.info(f"Created portal session for user {user_id[:8]}...")
        return session

    # =========================================================================
    # Subscription Management
    # =========================================================================

    async def get_subscription(self, user_id: str) -> Optional[SubscriptionInfo]:
        """
        Get user's active subscription.

        Args:
            user_id: Supabase auth user ID

        Returns:
            Subscription info or None
        """
        result = await self.db.execute_query(
            "subscriptions",
            "select",
            filters={"user_id": user_id},
            order={"column": "created_at", "ascending": False},
            limit=1,
        )

        if not result:
            return None

        sub = result[0]
        if sub["status"] not in ("active", "trialing", "past_due"):
            return None

        # Get tier features
        tier_info = await self.get_tier_info(sub["tier"])

        return SubscriptionInfo(
            id=sub["id"],
            user_id=sub["user_id"],
            stripe_subscription_id=sub["stripe_subscription_id"],
            tier=sub["tier"],
            status=sub["status"],
            current_period_start=datetime.fromisoformat(sub["current_period_start"].replace("Z", "+00:00")),
            current_period_end=datetime.fromisoformat(sub["current_period_end"].replace("Z", "+00:00")),
            cancel_at_period_end=sub.get("cancel_at_period_end", False),
            features=tier_info.features if tier_info else {},
        )

    async def sync_subscription_from_stripe(
        self,
        stripe_subscription: StripeSubscription,
        user_id: str,
    ) -> SubscriptionInfo:
        """
        Sync subscription data from Stripe webhook to database.

        Called by webhook handler after subscription events.

        Args:
            stripe_subscription: Subscription data from Stripe
            user_id: Supabase auth user ID

        Returns:
            Updated subscription info
        """
        # Determine tier from price ID
        tier = await self._get_tier_from_price(stripe_subscription.items[0]["price_id"])

        # Upsert subscription
        data = {
            "user_id": user_id,
            "stripe_subscription_id": stripe_subscription.id,
            "stripe_price_id": stripe_subscription.items[0]["price_id"],
            "tier": tier,
            "status": stripe_subscription.status,
            "current_period_start": datetime.fromtimestamp(
                stripe_subscription.current_period_start, tz=timezone.utc
            ).isoformat(),
            "current_period_end": datetime.fromtimestamp(
                stripe_subscription.current_period_end, tz=timezone.utc
            ).isoformat(),
            "cancel_at_period_end": stripe_subscription.cancel_at_period_end,
            "canceled_at": datetime.fromtimestamp(
                stripe_subscription.canceled_at, tz=timezone.utc
            ).isoformat() if stripe_subscription.canceled_at else None,
            "trial_start": datetime.fromtimestamp(
                stripe_subscription.trial_start, tz=timezone.utc
            ).isoformat() if stripe_subscription.trial_start else None,
            "trial_end": datetime.fromtimestamp(
                stripe_subscription.trial_end, tz=timezone.utc
            ).isoformat() if stripe_subscription.trial_end else None,
        }

        # Check if subscription exists
        existing = await self.db.execute_query(
            "subscriptions",
            "select",
            filters={"stripe_subscription_id": stripe_subscription.id},
        )

        if existing:
            result = await self.db.execute_query(
                "subscriptions",
                "update",
                data=data,
                filters={"stripe_subscription_id": stripe_subscription.id},
            )
        else:
            result = await self.db.execute_query(
                "subscriptions",
                "insert",
                data=data,
            )

        logger.info(f"Synced subscription {stripe_subscription.id} for user {user_id[:8]}...")

        tier_info = await self.get_tier_info(tier)
        return SubscriptionInfo(
            id=result[0]["id"],
            user_id=user_id,
            stripe_subscription_id=stripe_subscription.id,
            tier=tier,
            status=stripe_subscription.status,
            current_period_start=datetime.fromtimestamp(
                stripe_subscription.current_period_start, tz=timezone.utc
            ),
            current_period_end=datetime.fromtimestamp(
                stripe_subscription.current_period_end, tz=timezone.utc
            ),
            cancel_at_period_end=stripe_subscription.cancel_at_period_end,
            features=tier_info.features if tier_info else {},
        )

    async def _get_tier_from_price(self, price_id: str) -> str:
        """Map Stripe price ID to tier name."""
        result = await self.db.execute_query(
            "tier_limits",
            "select",
            filters={"stripe_price_id": price_id},
        )

        if result:
            return result[0]["tier"]

        # Default to free if price not found
        logger.warning(f"Unknown price ID: {price_id}, defaulting to free tier")
        return "free"

    # =========================================================================
    # Usage Tracking
    # =========================================================================

    async def get_current_usage(self, user_id: str) -> UsageInfo:
        """
        Get current period usage for a user.

        Args:
            user_id: Supabase auth user ID

        Returns:
            Current usage information
        """
        # Call the database function that gets or creates usage record
        result = await self.db.client.rpc(
            "get_or_create_usage_record",
            {"p_user_id": user_id},
        ).execute()

        if not result.data:
            # Return default usage for new users
            period_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            period_end = (period_start.replace(month=period_start.month + 1)
                         if period_start.month < 12
                         else period_start.replace(year=period_start.year + 1, month=1))

            return UsageInfo(
                user_id=user_id,
                period_start=period_start,
                period_end=period_end,
                tokens_used=0,
                tokens_limit=10000,  # Free tier default
                tokens_remaining=10000,
                usage_percentage=0.0,
                requests_count=0,
                requests_limit=100,
                estimated_cost_cents=0,
                cache_hits=0,
                cache_misses=0,
            )

        usage = result.data
        tokens_used = usage.get("tokens_used", 0)
        tokens_limit = usage.get("tokens_limit", 10000)

        return UsageInfo(
            user_id=user_id,
            period_start=datetime.fromisoformat(usage["period_start"].replace("Z", "+00:00")),
            period_end=datetime.fromisoformat(usage["period_end"].replace("Z", "+00:00")),
            tokens_used=tokens_used,
            tokens_limit=tokens_limit,
            tokens_remaining=max(0, tokens_limit - tokens_used),
            usage_percentage=round((tokens_used / tokens_limit) * 100, 2) if tokens_limit > 0 else 0,
            requests_count=usage.get("requests_count", 0),
            requests_limit=usage.get("requests_limit"),
            estimated_cost_cents=usage.get("estimated_cost_cents", 0),
            cache_hits=usage.get("cache_hits", 0),
            cache_misses=usage.get("cache_misses", 0),
        )

    async def record_usage(
        self,
        user_id: str,
        tokens: int,
        cost_cents: int = 0,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        is_cache_hit: bool = False,
    ) -> QuotaStatus:
        """
        Record token usage for a user.

        Args:
            user_id: Supabase auth user ID
            tokens: Number of tokens used
            cost_cents: Estimated cost in cents
            provider: AI provider name (e.g., "anthropic")
            model: Model name (e.g., "claude-3-5-sonnet")
            is_cache_hit: Whether response came from cache

        Returns:
            Updated quota status
        """
        # Call the database function to increment usage
        result = await self.db.client.rpc(
            "increment_usage",
            {
                "p_user_id": user_id,
                "p_tokens": tokens,
                "p_cost_cents": cost_cents,
                "p_provider": provider,
                "p_model": model,
                "p_is_cache_hit": is_cache_hit,
            },
        ).execute()

        if not result.data:
            raise ValueError(f"Failed to record usage for user {user_id}")

        data = result.data[0] if isinstance(result.data, list) else result.data

        # Get subscription for tier info
        subscription = await self.get_subscription(user_id)

        return QuotaStatus(
            has_quota=not data.get("is_over_limit", False),
            tokens_used=data.get("tokens_used", 0),
            tokens_limit=data.get("tokens_limit", 10000),
            tokens_remaining=data.get("tokens_remaining", 0),
            usage_percentage=round(
                (data.get("tokens_used", 0) / data.get("tokens_limit", 10000)) * 100, 2
            ),
            tier=subscription.tier if subscription else "free",
            period_ends_at=subscription.current_period_end if subscription else datetime.now(timezone.utc),
        )

    async def check_quota(self, user_id: str) -> QuotaStatus:
        """
        Check if user has remaining quota.

        Args:
            user_id: Supabase auth user ID

        Returns:
            Quota status with upgrade URL if exceeded
        """
        # Call the database function
        result = await self.db.client.rpc(
            "check_quota",
            {"p_user_id": user_id},
        ).execute()

        if not result.data:
            # Default response for users without subscription
            return QuotaStatus(
                has_quota=True,
                tokens_used=0,
                tokens_limit=10000,
                tokens_remaining=10000,
                usage_percentage=0.0,
                tier="free",
                period_ends_at=datetime.now(timezone.utc),
            )

        data = result.data[0] if isinstance(result.data, list) else result.data

        quota_status = QuotaStatus(
            has_quota=data.get("has_quota", True),
            tokens_used=data.get("tokens_used", 0),
            tokens_limit=data.get("tokens_limit", 10000),
            tokens_remaining=data.get("tokens_remaining", 10000),
            usage_percentage=data.get("usage_percentage", 0.0),
            tier=data.get("tier", "free"),
            period_ends_at=datetime.fromisoformat(
                data["period_ends_at"].replace("Z", "+00:00")
            ) if data.get("period_ends_at") else datetime.now(timezone.utc),
        )

        # Add upgrade URL if quota exceeded
        if not quota_status.has_quota:
            quota_status.upgrade_url = "/billing/upgrade"

        return quota_status

    # =========================================================================
    # Tier Information
    # =========================================================================

    async def get_tier_info(self, tier: str) -> Optional[TierInfo]:
        """
        Get tier limits and features.

        Args:
            tier: Tier name (free, pro, business, enterprise)

        Returns:
            Tier information or None if not found
        """
        result = await self.db.execute_query(
            "tier_limits",
            "select",
            filters={"tier": tier},
        )

        if not result:
            return None

        data = result[0]
        return TierInfo(
            tier=data["tier"],
            monthly_token_limit=data["monthly_token_limit"],
            monthly_request_limit=data.get("monthly_request_limit"),
            rate_limit_per_minute=data["rate_limit_per_minute"],
            rate_limit_per_day=data["rate_limit_per_day"],
            features=data.get("features", {}),
            price_usd_monthly=float(data["price_usd_monthly"]) if data.get("price_usd_monthly") else None,
            stripe_price_id=data.get("stripe_price_id"),
        )

    async def list_tiers(self) -> List[TierInfo]:
        """
        List all available subscription tiers.

        Returns:
            List of tier information
        """
        result = await self.db.execute_query(
            "tier_limits",
            "select",
        )

        return [
            TierInfo(
                tier=data["tier"],
                monthly_token_limit=data["monthly_token_limit"],
                monthly_request_limit=data.get("monthly_request_limit"),
                rate_limit_per_minute=data["rate_limit_per_minute"],
                rate_limit_per_day=data["rate_limit_per_day"],
                features=data.get("features", {}),
                price_usd_monthly=float(data["price_usd_monthly"]) if data.get("price_usd_monthly") else None,
                stripe_price_id=data.get("stripe_price_id"),
            )
            for data in result
        ]

    # =========================================================================
    # Billing Summary
    # =========================================================================

    async def get_billing_summary(self, user_id: str) -> BillingSummary:
        """
        Get comprehensive billing summary for dashboard display.

        Args:
            user_id: Supabase auth user ID

        Returns:
            Complete billing summary
        """
        customer = await self.get_customer(user_id)
        subscription = await self.get_subscription(user_id)
        usage = await self.get_current_usage(user_id)

        tier = subscription.tier if subscription else "free"
        tier_info = await self.get_tier_info(tier)

        # Get upcoming invoice if customer exists
        amount_due = None
        next_invoice_date = None
        if customer:
            try:
                upcoming = await self.stripe.get_upcoming_invoice(customer.stripe_customer_id)
                if upcoming:
                    amount_due = upcoming.amount_due
                    next_invoice_date = subscription.current_period_end if subscription else None
            except Exception:
                pass  # No upcoming invoice

        return BillingSummary(
            customer_id=customer.id if customer else None,
            stripe_customer_id=customer.stripe_customer_id if customer else None,
            subscription=subscription,
            usage=usage,
            tier=tier,
            features=tier_info.features if tier_info else {},
            next_invoice_date=next_invoice_date,
            amount_due_cents=amount_due,
        )

    # =========================================================================
    # Invoice History
    # =========================================================================

    async def list_invoices(
        self,
        user_id: str,
        limit: int = 10,
    ) -> List[StripeInvoice]:
        """
        List invoices for a user.

        Args:
            user_id: Supabase auth user ID
            limit: Maximum number of invoices

        Returns:
            List of invoices
        """
        customer = await self.get_customer(user_id)
        if not customer:
            return []

        return await self.stripe.list_invoices(
            customer_id=customer.stripe_customer_id,
            limit=limit,
        )
