"""
Billing Router

REST API endpoints for subscription management, usage tracking, and Stripe integration.

All endpoints require JWT authentication except the webhook endpoint.

Endpoints:
- POST /billing/checkout       - Create Stripe checkout session
- POST /billing/portal         - Create customer portal session
- GET  /billing/subscription   - Get current subscription
- GET  /billing/usage          - Get current period usage
- GET  /billing/quota          - Check quota status
- GET  /billing/tiers          - List available subscription tiers
- GET  /billing/invoices       - Get invoice history
- GET  /billing/summary        - Get billing summary for dashboard
- POST /billing/webhook        - Stripe webhook receiver (no auth)
"""

import os
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, HttpUrl

from app.auth import get_current_user_id, get_current_user
from app.services.billing_service import (
    BillingService,
    SubscriptionInfo,
    UsageInfo,
    QuotaStatus,
    BillingSummary,
    TierInfo,
)
from app.billing import StripeClient, WebhookHandler, WebhookResult
from app.billing.stripe_client import StripeCheckoutSession, StripeBillingPortalSession, StripeInvoice
from app.database.supabase_client import SupabaseClient

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/billing",
    tags=["billing"],
)

# Module-level service instances (initialized by main.py)
_billing_service: BillingService | None = None
_stripe_client: StripeClient | None = None
_supabase_client: SupabaseClient | None = None


def get_billing_service() -> BillingService:
    """Get the billing service instance."""
    if _billing_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing service not initialized",
        )
    return _billing_service


def get_stripe_client() -> StripeClient:
    """Get the Stripe client instance."""
    if _stripe_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe client not initialized",
        )
    return _stripe_client


def init_billing_router(
    billing_service: BillingService,
    stripe_client: StripeClient,
    supabase_client: SupabaseClient,
) -> None:
    """
    Initialize billing router with service instances.

    Call this in main.py lifespan handler:
        from app.routers.billing import init_billing_router
        init_billing_router(billing_service, stripe_client, supabase_client)
    """
    global _billing_service, _stripe_client, _supabase_client
    _billing_service = billing_service
    _stripe_client = stripe_client
    _supabase_client = supabase_client
    logger.info("Billing router initialized")


# =============================================================================
# Request/Response Models
# =============================================================================

class CreateCheckoutRequest(BaseModel):
    """Request to create a checkout session."""
    price_id: str = Field(..., description="Stripe price ID for the plan")
    success_url: str = Field(..., description="URL to redirect after successful payment")
    cancel_url: str = Field(..., description="URL to redirect if user cancels")
    trial_days: Optional[int] = Field(None, ge=1, le=30, description="Trial period in days")


class CreateCheckoutResponse(BaseModel):
    """Response with checkout session details."""
    session_id: str
    checkout_url: str
    mode: str = "subscription"


class CreatePortalRequest(BaseModel):
    """Request to create a billing portal session."""
    return_url: str = Field(..., description="URL to return to after portal session")


class CreatePortalResponse(BaseModel):
    """Response with portal session details."""
    session_id: str
    portal_url: str


class QuotaCheckResponse(BaseModel):
    """Response with quota check results."""
    has_quota: bool
    tokens_used: int
    tokens_limit: int
    tokens_remaining: int
    usage_percentage: float
    tier: str
    period_ends_at: str
    upgrade_url: Optional[str] = None


class InvoiceResponse(BaseModel):
    """Invoice details for API response."""
    id: str
    status: str
    total_cents: int
    currency: str
    created_at: str
    paid_at: Optional[str] = None
    hosted_url: Optional[str] = None
    pdf_url: Optional[str] = None


# =============================================================================
# Checkout & Portal Endpoints
# =============================================================================

@router.post(
    "/checkout",
    response_model=CreateCheckoutResponse,
    summary="Create Stripe checkout session",
    responses={
        200: {"description": "Checkout session created successfully"},
    },
)
async def create_checkout(
    request: CreateCheckoutRequest,
    user: dict = Depends(get_current_user),
    service: BillingService = Depends(get_billing_service),
):
    """
    Create a Stripe Checkout session for subscription purchase.

    Returns a checkout URL to redirect the user to Stripe's hosted payment page.
    After payment, user is redirected to success_url with session_id query param.
    """
    try:
        session = await service.create_checkout_session(
            user_id=user["sub"],
            email=user.get("email", ""),
            price_id=request.price_id,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            trial_days=request.trial_days,
        )

        logger.info(f"Created checkout session for user {user['sub'][:8]}...")
        return CreateCheckoutResponse(
            session_id=session.id,
            checkout_url=session.url,
            mode=session.mode,
        )
    except Exception as e:
        logger.error(f"Failed to create checkout session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session",
        )


@router.post(
    "/portal",
    response_model=CreatePortalResponse,
    summary="Create billing portal session",
    responses={
        200: {"description": "Portal session created successfully"},
        404: {"description": "No billing account found"},
    },
)
async def create_portal(
    request: CreatePortalRequest,
    user_id: str = Depends(get_current_user_id),
    service: BillingService = Depends(get_billing_service),
):
    """
    Create a Stripe Billing Portal session for self-service management.

    Allows users to:
    - View and update payment methods
    - View invoice history
    - Cancel or modify subscription
    - Download invoices/receipts
    """
    try:
        session = await service.create_portal_session(
            user_id=user_id,
            return_url=request.return_url,
        )

        logger.info(f"Created portal session for user {user_id[:8]}...")
        return CreatePortalResponse(
            session_id=session.id,
            portal_url=session.url,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to create portal session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create portal session",
        )


# =============================================================================
# Subscription & Usage Endpoints
# =============================================================================

@router.get(
    "/subscription",
    response_model=Optional[SubscriptionInfo],
    summary="Get current subscription",
    responses={
        200: {"description": "Returns subscription info or null if none"},
    },
)
async def get_subscription(
    user_id: str = Depends(get_current_user_id),
    service: BillingService = Depends(get_billing_service),
):
    """
    Get the current user's subscription details.

    Returns null if user has no active subscription (free tier).
    """
    return await service.get_subscription(user_id)


@router.get(
    "/usage",
    response_model=UsageInfo,
    summary="Get current period usage",
)
async def get_usage(
    user_id: str = Depends(get_current_user_id),
    service: BillingService = Depends(get_billing_service),
):
    """
    Get token and request usage for the current billing period.

    Includes:
    - Tokens used and remaining
    - Request count
    - Estimated cost
    - Cache performance metrics
    """
    return await service.get_current_usage(user_id)


@router.get(
    "/quota",
    response_model=QuotaCheckResponse,
    summary="Check quota status",
)
async def check_quota(
    user_id: str = Depends(get_current_user_id),
    service: BillingService = Depends(get_billing_service),
):
    """
    Check if user has remaining quota for the current period.

    Use this before making API calls to avoid 429 errors.
    Returns upgrade_url if quota is exceeded.
    """
    quota = await service.check_quota(user_id)

    return QuotaCheckResponse(
        has_quota=quota.has_quota,
        tokens_used=quota.tokens_used,
        tokens_limit=quota.tokens_limit,
        tokens_remaining=quota.tokens_remaining,
        usage_percentage=quota.usage_percentage,
        tier=quota.tier,
        period_ends_at=quota.period_ends_at.isoformat(),
        upgrade_url=quota.upgrade_url,
    )


# =============================================================================
# Tier & Pricing Endpoints
# =============================================================================

@router.get(
    "/tiers",
    response_model=List[TierInfo],
    summary="List subscription tiers",
)
async def list_tiers(
    service: BillingService = Depends(get_billing_service),
):
    """
    List all available subscription tiers with limits and pricing.

    Use this to display pricing page or upgrade options.
    """
    return await service.list_tiers()


@router.get(
    "/tiers/{tier}",
    response_model=TierInfo,
    summary="Get tier details",
    responses={
        404: {"description": "Tier not found"},
    },
)
async def get_tier(
    tier: str,
    service: BillingService = Depends(get_billing_service),
):
    """
    Get details for a specific subscription tier.
    """
    result = await service.get_tier_info(tier)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tier '{tier}' not found",
        )
    return result


# =============================================================================
# Invoice & Summary Endpoints
# =============================================================================

@router.get(
    "/invoices",
    response_model=List[InvoiceResponse],
    summary="Get invoice history",
)
async def list_invoices(
    limit: int = 10,
    user_id: str = Depends(get_current_user_id),
    service: BillingService = Depends(get_billing_service),
):
    """
    Get invoice history for the current user.

    Returns the most recent invoices with links to hosted views and PDFs.
    """
    invoices = await service.list_invoices(user_id, limit=limit)

    return [
        InvoiceResponse(
            id=inv.id,
            status=inv.status,
            total_cents=inv.total,
            currency=inv.currency,
            created_at=str(inv.created),
            paid_at=str(inv.paid_at) if inv.paid_at else None,
            hosted_url=inv.hosted_invoice_url,
            pdf_url=inv.invoice_pdf,
        )
        for inv in invoices
    ]


@router.get(
    "/summary",
    response_model=BillingSummary,
    summary="Get billing summary",
)
async def get_billing_summary(
    user_id: str = Depends(get_current_user_id),
    service: BillingService = Depends(get_billing_service),
):
    """
    Get comprehensive billing summary for dashboard display.

    Includes subscription, usage, tier features, and next invoice details.
    """
    return await service.get_billing_summary(user_id)


# =============================================================================
# Webhook Endpoint
# =============================================================================

@router.post(
    "/webhook",
    response_model=WebhookResult,
    summary="Stripe webhook receiver",
    include_in_schema=False,  # Hide from public API docs
)
async def stripe_webhook(request: Request):
    """
    Receive and process Stripe webhook events.

    This endpoint is called by Stripe to notify of subscription changes,
    payment events, and other billing-related activities.

    **Note**: This endpoint does not require authentication.
    Webhook signature verification is used instead.
    """
    if _billing_service is None or _stripe_client is None or _supabase_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing service not initialized",
        )

    handler = WebhookHandler(
        stripe_client=_stripe_client,
        billing_service=_billing_service,
        supabase_client=_supabase_client,
    )

    return await handler.handle_webhook(request)


# =============================================================================
# Utility Endpoints
# =============================================================================

@router.get(
    "/health",
    summary="Check billing service health",
    include_in_schema=False,
)
async def billing_health():
    """Check if billing services are properly initialized."""
    return {
        "billing_service": _billing_service is not None,
        "stripe_client": _stripe_client is not None,
        "supabase_client": _supabase_client is not None,
        "status": "healthy" if all([_billing_service, _stripe_client, _supabase_client]) else "degraded",
    }
