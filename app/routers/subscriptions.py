"""
Subscription Tracking Router

REST API endpoints for SaaS subscription management.
All endpoints require JWT authentication with RLS-based data isolation.

Endpoints:
- POST   /subscriptions          - Add subscription
- GET    /subscriptions          - List all subscriptions (with filters)
- GET    /subscriptions/summary  - Monthly spend summary
- GET    /subscriptions/upcoming - Upcoming billing alerts
- GET    /subscriptions/{id}     - Get subscription details
- PUT    /subscriptions/{id}     - Update subscription
- DELETE /subscriptions/{id}     - Cancel/remove subscription
- POST   /subscriptions/{id}/usage - Record usage (for usage-based billing)
- GET    /subscriptions/{id}/usage - Get usage history
- POST   /subscriptions/import   - Bulk import from CSV
"""

import logging
from typing import Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.models.subscription import (
    SubscriptionCreate, SubscriptionUpdate, SubscriptionResponse,
    SubscriptionListResponse, SubscriptionUsageCreate, SubscriptionUsageResponse,
    UpcomingBillingListResponse, SpendSummary, SubscriptionImportResult,
    ServiceCategory, SubscriptionStatus, BillingCycle
)
from app.services.subscription_service import SubscriptionService, get_subscription_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/subscriptions",
    tags=["subscriptions"],
)


# =============================================================================
# Response Models
# =============================================================================

class UsageHistoryResponse(BaseModel):
    """List of usage records."""
    usage: list[SubscriptionUsageResponse]
    total_usage: Decimal
    total_cost: Decimal


class ImportRequest(BaseModel):
    """Request model for CSV import."""
    csv_data: str = Field(..., description="CSV data as string")
    skip_duplicates: bool = Field(default=True, description="Skip existing subscriptions")


class DeleteResponse(BaseModel):
    """Response for delete operation."""
    deleted: bool
    message: str


# =============================================================================
# Subscription CRUD Endpoints
# =============================================================================

@router.post(
    "",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add subscription",
    description="Add a new SaaS subscription to track. Duplicate service names are not allowed."
)
async def create_subscription(
    request: SubscriptionCreate,
    user_id: str = Depends(get_current_user_id),
    service: SubscriptionService = Depends(get_subscription_service),
):
    """
    Add a new subscription.

    The monthly_cost is used for spend summaries. If you have a yearly subscription,
    set billing_cycle to "yearly" and the monthly_cost to the monthly equivalent
    (yearly_price / 12).
    """
    try:
        subscription = await service.create_subscription(user_id, request)
        logger.info(f"Created subscription: {subscription.service_name} for user {user_id}")
        return subscription
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "",
    response_model=SubscriptionListResponse,
    summary="List subscriptions",
    description="Get all subscriptions with optional filters by category, status, or search term."
)
async def list_subscriptions(
    category: Optional[ServiceCategory] = Query(None, description="Filter by category"),
    subscription_status: Optional[SubscriptionStatus] = Query(None, alias="status", description="Filter by status"),
    search: Optional[str] = Query(None, description="Search in service name"),
    limit: int = Query(100, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    user_id: str = Depends(get_current_user_id),
    service: SubscriptionService = Depends(get_subscription_service),
):
    """
    List all subscriptions for the authenticated user.

    Supports filtering by category (e.g., llm_provider, infrastructure) and
    status (active, trial, cancelled, paused, past_due).
    """
    subscriptions = await service.get_subscriptions(
        user_id=user_id,
        category=category,
        status=subscription_status,
        search=search,
        limit=limit,
        offset=offset
    )

    return SubscriptionListResponse(
        subscriptions=subscriptions,
        total=len(subscriptions)
    )


@router.get(
    "/summary",
    response_model=SpendSummary,
    summary="Get spend summary",
    description="Get monthly and yearly spend totals with breakdown by category."
)
async def get_spend_summary(
    user_id: str = Depends(get_current_user_id),
    service: SubscriptionService = Depends(get_subscription_service),
):
    """
    Get monthly spend summary.

    Returns total monthly and yearly costs, active subscription count,
    and breakdown by category. Uses the database function for efficiency.
    """
    summary = await service.get_spend_summary(user_id)
    return summary


@router.get(
    "/upcoming",
    response_model=UpcomingBillingListResponse,
    summary="Get upcoming billing alerts",
    description="Get subscriptions due for billing soon based on alert_days_before setting."
)
async def get_upcoming_alerts(
    user_id: str = Depends(get_current_user_id),
    service: SubscriptionService = Depends(get_subscription_service),
):
    """
    Get upcoming billing alerts.

    Returns subscriptions that are due for billing within their configured
    alert_days_before window. Each alert includes urgency level (critical,
    high, medium, low) based on days until billing.
    """
    alerts = await service.get_upcoming_alerts(user_id)
    return alerts


@router.get(
    "/{subscription_id}",
    response_model=SubscriptionResponse,
    summary="Get subscription",
    description="Get details of a specific subscription."
)
async def get_subscription(
    subscription_id: str,
    user_id: str = Depends(get_current_user_id),
    service: SubscriptionService = Depends(get_subscription_service),
):
    """
    Get subscription details by ID.
    """
    subscription = await service.get_subscription(user_id, subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    return subscription


@router.put(
    "/{subscription_id}",
    response_model=SubscriptionResponse,
    summary="Update subscription",
    description="Update subscription details. Only provided fields are updated."
)
async def update_subscription(
    subscription_id: str,
    request: SubscriptionUpdate,
    user_id: str = Depends(get_current_user_id),
    service: SubscriptionService = Depends(get_subscription_service),
):
    """
    Update a subscription.

    Only fields that are provided will be updated. Use this to change
    pricing, billing dates, status, or alert settings.
    """
    try:
        subscription = await service.update_subscription(user_id, subscription_id, request)
        logger.info(f"Updated subscription: {subscription_id} for user {user_id}")
        return subscription
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.delete(
    "/{subscription_id}",
    response_model=DeleteResponse,
    summary="Delete subscription",
    description="Remove a subscription from tracking. This does not cancel the actual subscription."
)
async def delete_subscription(
    subscription_id: str,
    user_id: str = Depends(get_current_user_id),
    service: SubscriptionService = Depends(get_subscription_service),
):
    """
    Delete a subscription.

    This removes the subscription from tracking. It does NOT cancel your
    actual subscription with the service provider.
    """
    deleted = await service.delete_subscription(user_id, subscription_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )

    logger.info(f"Deleted subscription: {subscription_id} for user {user_id}")
    return DeleteResponse(deleted=True, message="Subscription deleted successfully")


# =============================================================================
# Usage Tracking Endpoints
# =============================================================================

@router.post(
    "/{subscription_id}/usage",
    response_model=SubscriptionUsageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record usage",
    description="Record usage for a usage-based subscription (e.g., API calls, tokens)."
)
async def record_usage(
    subscription_id: str,
    request: SubscriptionUsageCreate,
    user_id: str = Depends(get_current_user_id),
    service: SubscriptionService = Depends(get_subscription_service),
):
    """
    Record usage for a usage-based subscription.

    Use this for subscriptions with billing_cycle='usage_based' to track
    consumption over time. Each record represents usage for a specific period.
    """
    # Verify subscription exists and belongs to user
    subscription = await service.get_subscription(user_id, subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )

    try:
        usage = await service.record_usage(user_id, subscription_id, request)
        logger.info(f"Recorded usage for subscription: {subscription_id}")
        return usage
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/{subscription_id}/usage",
    response_model=UsageHistoryResponse,
    summary="Get usage history",
    description="Get usage history for a subscription."
)
async def get_usage_history(
    subscription_id: str,
    limit: int = Query(12, ge=1, le=100, description="Max records to return"),
    user_id: str = Depends(get_current_user_id),
    service: SubscriptionService = Depends(get_subscription_service),
):
    """
    Get usage history for a subscription.

    Returns usage records sorted by period end date (most recent first).
    Includes total usage and cost across all returned records.
    """
    # Verify subscription exists
    subscription = await service.get_subscription(user_id, subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )

    usage_records = await service.get_usage_history(user_id, subscription_id, limit)

    total_usage = sum(u.usage_amount for u in usage_records)
    total_cost = sum(u.cost_usd for u in usage_records)

    return UsageHistoryResponse(
        usage=usage_records,
        total_usage=total_usage,
        total_cost=total_cost
    )


# =============================================================================
# Import Endpoints
# =============================================================================

@router.post(
    "/import",
    response_model=SubscriptionImportResult,
    summary="Import subscriptions from CSV",
    description="Bulk import subscriptions from CSV data."
)
async def import_subscriptions(
    request: ImportRequest,
    user_id: str = Depends(get_current_user_id),
    service: SubscriptionService = Depends(get_subscription_service),
):
    """
    Import subscriptions from CSV data.

    Expected CSV format:
    ```
    service_name,monthly_cost,billing_cycle,category,billing_day,notes
    Anthropic,100.00,monthly,llm_provider,15,Claude API
    Vercel,20.00,monthly,infrastructure,,Hosting
    ```

    Required columns: service_name, monthly_cost
    Optional columns: billing_cycle, category, billing_day, notes

    Set skip_duplicates=true (default) to skip existing subscriptions,
    or skip_duplicates=false to get errors for duplicates.
    """
    result = await service.import_subscriptions(
        user_id=user_id,
        csv_data=request.csv_data,
        skip_duplicates=request.skip_duplicates
    )

    logger.info(
        f"Import complete for user {user_id}: "
        f"imported={result.imported}, skipped={result.skipped}, errors={len(result.errors)}"
    )

    return result


@router.post(
    "/import/file",
    response_model=SubscriptionImportResult,
    summary="Import subscriptions from CSV file",
    description="Upload a CSV file to bulk import subscriptions."
)
async def import_subscriptions_file(
    file: UploadFile = File(..., description="CSV file to import"),
    skip_duplicates: bool = Query(True, description="Skip existing subscriptions"),
    user_id: str = Depends(get_current_user_id),
    service: SubscriptionService = Depends(get_subscription_service),
):
    """
    Import subscriptions from uploaded CSV file.

    Same format as the /import endpoint, but accepts a file upload
    instead of raw CSV string.
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV file"
        )

    try:
        contents = await file.read()
        csv_data = contents.decode('utf-8')
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be UTF-8 encoded"
        )

    result = await service.import_subscriptions(
        user_id=user_id,
        csv_data=csv_data,
        skip_duplicates=skip_duplicates
    )

    logger.info(
        f"File import complete for user {user_id}: "
        f"imported={result.imported}, skipped={result.skipped}, errors={len(result.errors)}"
    )

    return result
