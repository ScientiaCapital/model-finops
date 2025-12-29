"""
Subscription Service

Async service layer for SaaS subscription tracking.
Uses Supabase client pattern with RLS for multi-tenant security.

Features:
- CRUD operations for subscriptions
- Spend summary using database functions
- Upcoming billing alerts
- Usage recording for usage-based billing
- Bulk import from CSV data
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, date
from decimal import Decimal
import csv
import io

from app.models.subscription import (
    SubscriptionCreate, SubscriptionUpdate, SubscriptionResponse,
    SubscriptionUsageCreate, SubscriptionUsageResponse,
    SubscriptionAlertCreate, SubscriptionAlertResponse,
    UpcomingBillingAlert, UpcomingBillingListResponse,
    SpendSummary, SubscriptionImportRow, SubscriptionImportResult,
    ServiceCategory, BillingCycle, SubscriptionStatus
)

logger = logging.getLogger(__name__)


class SubscriptionService:
    """
    Subscription tracking service.

    Handles:
    - Subscription CRUD operations
    - Spend summaries and analytics
    - Billing alerts
    - Usage tracking for metered billing
    - Bulk import
    """

    def __init__(self, supabase_client=None):
        """
        Initialize subscription service.

        Args:
            supabase_client: Supabase client instance (or mock for testing)
        """
        self._supabase = supabase_client

    @property
    def supabase(self):
        """Lazy load Supabase client."""
        if self._supabase is None:
            from app.database.supabase_client import get_supabase_client
            self._supabase = get_supabase_client()
        return self._supabase

    # =========================================================================
    # Subscription CRUD
    # =========================================================================

    async def create_subscription(
        self,
        user_id: str,
        data: SubscriptionCreate
    ) -> SubscriptionResponse:
        """
        Create a new subscription.

        Args:
            user_id: User ID (from JWT)
            data: Subscription creation data

        Returns:
            Created subscription

        Raises:
            ValueError: If subscription already exists for this service
        """
        insert_data = {
            "user_id": user_id,
            "service_name": data.service_name,
            "service_provider": data.service_provider,
            "category": data.category.value if isinstance(data.category, ServiceCategory) else data.category,
            "monthly_cost": float(data.monthly_cost),
            "original_price": float(data.original_price) if data.original_price else None,
            "currency": data.currency,
            "billing_cycle": data.billing_cycle.value if isinstance(data.billing_cycle, BillingCycle) else data.billing_cycle,
            "billing_day": data.billing_day,
            "next_billing_date": data.next_billing_date.isoformat() if data.next_billing_date else None,
            "trial_ends_at": data.trial_ends_at.isoformat() if data.trial_ends_at else None,
            "status": data.status.value if isinstance(data.status, SubscriptionStatus) else data.status,
            "auto_renew": data.auto_renew,
            "alert_days_before": data.alert_days_before,
            "alert_enabled": data.alert_enabled,
            "notes": data.notes,
            "api_key_configured": data.api_key_configured,
            "external_subscription_id": data.external_subscription_id,
            "external_customer_id": data.external_customer_id,
        }

        # Remove None values
        insert_data = {k: v for k, v in insert_data.items() if v is not None}

        try:
            result = self.supabase.table("subscriptions").insert(insert_data).execute()

            if result.data:
                return self._map_to_response(result.data[0])

            raise ValueError("Failed to create subscription")

        except Exception as e:
            if "duplicate key" in str(e).lower() or "unique" in str(e).lower():
                raise ValueError(f"Subscription for '{data.service_name}' already exists")
            logger.error(f"Error creating subscription: {e}")
            raise

    async def get_subscriptions(
        self,
        user_id: str,
        category: Optional[ServiceCategory] = None,
        status: Optional[SubscriptionStatus] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[SubscriptionResponse]:
        """
        Get all subscriptions for a user with optional filters.

        Args:
            user_id: User ID
            category: Filter by category
            status: Filter by status
            search: Search in service name
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of subscriptions
        """
        query = self.supabase.table("subscriptions").select("*").eq("user_id", user_id)

        if category:
            cat_value = category.value if isinstance(category, ServiceCategory) else category
            query = query.eq("category", cat_value)

        if status:
            status_value = status.value if isinstance(status, SubscriptionStatus) else status
            query = query.eq("status", status_value)

        if search:
            query = query.ilike("service_name", f"%{search}%")

        query = query.order("service_name").range(offset, offset + limit - 1)

        result = query.execute()

        return [self._map_to_response(s) for s in result.data]

    async def get_subscription(
        self,
        user_id: str,
        subscription_id: str
    ) -> Optional[SubscriptionResponse]:
        """
        Get a single subscription by ID.

        Args:
            user_id: User ID
            subscription_id: Subscription ID

        Returns:
            Subscription or None if not found
        """
        result = self.supabase.table("subscriptions").select("*").eq(
            "id", subscription_id
        ).eq("user_id", user_id).execute()

        if result.data:
            return self._map_to_response(result.data[0])
        return None

    async def update_subscription(
        self,
        user_id: str,
        subscription_id: str,
        data: SubscriptionUpdate
    ) -> SubscriptionResponse:
        """
        Update a subscription.

        Args:
            user_id: User ID
            subscription_id: Subscription ID
            data: Update data

        Returns:
            Updated subscription

        Raises:
            ValueError: If subscription not found
        """
        update_data = {}

        # Only include fields that are set
        if data.service_name is not None:
            update_data["service_name"] = data.service_name
        if data.service_provider is not None:
            update_data["service_provider"] = data.service_provider
        if data.category is not None:
            update_data["category"] = data.category.value if isinstance(data.category, ServiceCategory) else data.category
        if data.monthly_cost is not None:
            update_data["monthly_cost"] = float(data.monthly_cost)
        if data.original_price is not None:
            update_data["original_price"] = float(data.original_price)
        if data.currency is not None:
            update_data["currency"] = data.currency
        if data.billing_cycle is not None:
            update_data["billing_cycle"] = data.billing_cycle.value if isinstance(data.billing_cycle, BillingCycle) else data.billing_cycle
        if data.billing_day is not None:
            update_data["billing_day"] = data.billing_day
        if data.next_billing_date is not None:
            update_data["next_billing_date"] = data.next_billing_date.isoformat()
        if data.trial_ends_at is not None:
            update_data["trial_ends_at"] = data.trial_ends_at.isoformat()
        if data.status is not None:
            update_data["status"] = data.status.value if isinstance(data.status, SubscriptionStatus) else data.status
        if data.auto_renew is not None:
            update_data["auto_renew"] = data.auto_renew
        if data.alert_days_before is not None:
            update_data["alert_days_before"] = data.alert_days_before
        if data.alert_enabled is not None:
            update_data["alert_enabled"] = data.alert_enabled
        if data.notes is not None:
            update_data["notes"] = data.notes
        if data.api_key_configured is not None:
            update_data["api_key_configured"] = data.api_key_configured
        if data.external_subscription_id is not None:
            update_data["external_subscription_id"] = data.external_subscription_id
        if data.external_customer_id is not None:
            update_data["external_customer_id"] = data.external_customer_id

        if not update_data:
            # No changes, return existing
            existing = await self.get_subscription(user_id, subscription_id)
            if existing:
                return existing
            raise ValueError("Subscription not found")

        result = self.supabase.table("subscriptions").update(update_data).eq(
            "id", subscription_id
        ).eq("user_id", user_id).execute()

        if result.data:
            return self._map_to_response(result.data[0])

        raise ValueError("Subscription not found")

    async def delete_subscription(
        self,
        user_id: str,
        subscription_id: str
    ) -> bool:
        """
        Delete (cancel) a subscription.

        Args:
            user_id: User ID
            subscription_id: Subscription ID

        Returns:
            True if deleted, False if not found
        """
        result = self.supabase.table("subscriptions").delete().eq(
            "id", subscription_id
        ).eq("user_id", user_id).execute()

        return len(result.data) > 0

    # =========================================================================
    # Spend Summary
    # =========================================================================

    async def get_spend_summary(self, user_id: str) -> SpendSummary:
        """
        Get monthly spend summary using the database function.

        Args:
            user_id: User ID

        Returns:
            Spend summary with totals and breakdown by category
        """
        result = self.supabase.rpc(
            "get_monthly_spend_summary",
            {"p_user_id": user_id}
        ).execute()

        if result.data and len(result.data) > 0:
            data = result.data[0]
            return SpendSummary(
                total_monthly_cost=Decimal(str(data.get("total_monthly_cost", 0))),
                total_yearly_cost=Decimal(str(data.get("total_yearly_cost", 0))),
                active_subscriptions=data.get("active_subscriptions", 0),
                by_category=data.get("by_category", {}) or {}
            )

        # No data, return empty summary
        return SpendSummary(
            total_monthly_cost=Decimal("0"),
            total_yearly_cost=Decimal("0"),
            active_subscriptions=0,
            by_category={}
        )

    # =========================================================================
    # Upcoming Billing Alerts
    # =========================================================================

    async def get_upcoming_alerts(
        self,
        user_id: str
    ) -> UpcomingBillingListResponse:
        """
        Get upcoming billing alerts using the database function.

        Args:
            user_id: User ID

        Returns:
            List of upcoming billing alerts
        """
        result = self.supabase.rpc(
            "get_upcoming_billing_alerts",
            {"p_user_id": user_id}
        ).execute()

        alerts = []
        total_cost = Decimal("0")

        for row in result.data or []:
            alert = UpcomingBillingAlert(
                subscription_id=row["subscription_id"],
                user_id=row["user_id"],
                service_name=row["service_name"],
                monthly_cost=Decimal(str(row.get("monthly_cost", 0))),
                next_billing_date=datetime.strptime(
                    row["next_billing_date"], "%Y-%m-%d"
                ).date() if isinstance(row["next_billing_date"], str) else row["next_billing_date"],
                days_until_billing=row.get("days_until_billing", 0),
                alert_days_before=row.get("alert_days_before", 3)
            )
            alerts.append(alert)
            total_cost += alert.monthly_cost

        return UpcomingBillingListResponse(
            alerts=alerts,
            total_upcoming_cost=total_cost
        )

    async def mark_alert_sent(
        self,
        subscription_id: str,
        user_id: str
    ) -> None:
        """
        Mark that an alert has been sent for a subscription.

        Args:
            subscription_id: Subscription ID
            user_id: User ID
        """
        self.supabase.table("subscriptions").update({
            "last_alert_sent_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", subscription_id).eq("user_id", user_id).execute()

    # =========================================================================
    # Usage Recording
    # =========================================================================

    async def record_usage(
        self,
        user_id: str,
        subscription_id: str,
        usage_data: SubscriptionUsageCreate
    ) -> SubscriptionUsageResponse:
        """
        Record usage for a usage-based subscription.

        Args:
            user_id: User ID
            subscription_id: Subscription ID
            usage_data: Usage data

        Returns:
            Created usage record
        """
        insert_data = {
            "subscription_id": subscription_id,
            "user_id": user_id,
            "period_start": usage_data.period_start.isoformat(),
            "period_end": usage_data.period_end.isoformat(),
            "usage_amount": float(usage_data.usage_amount),
            "usage_unit": usage_data.usage_unit,
            "cost_usd": float(usage_data.cost_usd),
            "breakdown": usage_data.breakdown
        }

        result = self.supabase.table("subscription_usage").insert(insert_data).execute()

        if result.data:
            return self._map_usage_to_response(result.data[0])

        raise ValueError("Failed to record usage")

    async def get_usage_history(
        self,
        user_id: str,
        subscription_id: str,
        limit: int = 12
    ) -> List[SubscriptionUsageResponse]:
        """
        Get usage history for a subscription.

        Args:
            user_id: User ID
            subscription_id: Subscription ID
            limit: Maximum records to return

        Returns:
            List of usage records, most recent first
        """
        result = self.supabase.table("subscription_usage").select("*").eq(
            "subscription_id", subscription_id
        ).eq("user_id", user_id).order(
            "period_end", desc=True
        ).limit(limit).execute()

        return [self._map_usage_to_response(u) for u in result.data]

    # =========================================================================
    # Alert History
    # =========================================================================

    async def create_alert_record(
        self,
        user_id: str,
        subscription_id: str,
        alert_data: SubscriptionAlertCreate
    ) -> SubscriptionAlertResponse:
        """
        Create an alert record for tracking.

        Args:
            user_id: User ID
            subscription_id: Subscription ID
            alert_data: Alert data

        Returns:
            Created alert record
        """
        insert_data = {
            "subscription_id": subscription_id,
            "user_id": user_id,
            "alert_type": alert_data.alert_type,
            "message": alert_data.message,
            "channels": alert_data.channels,
            "billing_date": alert_data.billing_date.isoformat() if alert_data.billing_date else None,
            "amount": float(alert_data.amount) if alert_data.amount else None,
            "delivery_status": "sent"
        }

        result = self.supabase.table("subscription_alerts").insert(insert_data).execute()

        if result.data:
            return self._map_alert_to_response(result.data[0])

        raise ValueError("Failed to create alert record")

    async def get_alert_history(
        self,
        user_id: str,
        subscription_id: Optional[str] = None,
        limit: int = 50
    ) -> List[SubscriptionAlertResponse]:
        """
        Get alert history.

        Args:
            user_id: User ID
            subscription_id: Optional filter by subscription
            limit: Maximum records

        Returns:
            List of alert records
        """
        query = self.supabase.table("subscription_alerts").select("*").eq("user_id", user_id)

        if subscription_id:
            query = query.eq("subscription_id", subscription_id)

        query = query.order("sent_at", desc=True).limit(limit)

        result = query.execute()

        return [self._map_alert_to_response(a) for a in result.data]

    # =========================================================================
    # Bulk Import
    # =========================================================================

    async def import_subscriptions(
        self,
        user_id: str,
        csv_data: str,
        skip_duplicates: bool = True
    ) -> SubscriptionImportResult:
        """
        Import subscriptions from CSV data.

        Expected CSV columns:
        - service_name (required)
        - monthly_cost (required)
        - billing_cycle (optional, default: monthly)
        - category (optional, default: other)
        - billing_day (optional)
        - notes (optional)

        Args:
            user_id: User ID
            csv_data: CSV string data
            skip_duplicates: Whether to skip existing subscriptions

        Returns:
            Import result with counts and any errors
        """
        imported = []
        skipped = 0
        errors = []

        try:
            reader = csv.DictReader(io.StringIO(csv_data))

            for row_num, row in enumerate(reader, start=2):  # Start at 2 (after header)
                try:
                    # Validate required fields
                    if not row.get("service_name"):
                        errors.append(f"Row {row_num}: Missing service_name")
                        continue

                    if not row.get("monthly_cost"):
                        errors.append(f"Row {row_num}: Missing monthly_cost")
                        continue

                    # Parse monthly cost
                    try:
                        monthly_cost = Decimal(row["monthly_cost"].replace("$", "").replace(",", ""))
                    except (ValueError, TypeError):
                        errors.append(f"Row {row_num}: Invalid monthly_cost '{row['monthly_cost']}'")
                        continue

                    # Parse billing cycle
                    billing_cycle = row.get("billing_cycle", "monthly").lower()
                    try:
                        billing_cycle_enum = BillingCycle(billing_cycle)
                    except ValueError:
                        billing_cycle_enum = BillingCycle.MONTHLY

                    # Parse category
                    category = row.get("category", "other").lower()
                    try:
                        category_enum = ServiceCategory(category)
                    except ValueError:
                        category_enum = ServiceCategory.OTHER

                    # Parse billing day
                    billing_day = None
                    if row.get("billing_day"):
                        try:
                            billing_day = int(row["billing_day"])
                            if billing_day < 1 or billing_day > 31:
                                billing_day = None
                        except ValueError:
                            pass

                    # Create subscription
                    create_data = SubscriptionCreate(
                        service_name=row["service_name"].strip(),
                        monthly_cost=monthly_cost,
                        billing_cycle=billing_cycle_enum,
                        category=category_enum,
                        billing_day=billing_day,
                        notes=row.get("notes", "").strip() or None
                    )

                    try:
                        subscription = await self.create_subscription(user_id, create_data)
                        imported.append(subscription)
                    except ValueError as e:
                        if "already exists" in str(e) and skip_duplicates:
                            skipped += 1
                        else:
                            errors.append(f"Row {row_num}: {str(e)}")

                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")

        except csv.Error as e:
            errors.append(f"CSV parsing error: {str(e)}")

        return SubscriptionImportResult(
            imported=len(imported),
            skipped=skipped,
            errors=errors,
            subscriptions=imported
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _map_to_response(self, data: Dict[str, Any]) -> SubscriptionResponse:
        """Map database row to response model."""
        return SubscriptionResponse(
            id=data["id"],
            user_id=data["user_id"],
            service_name=data["service_name"],
            service_provider=data.get("service_provider"),
            category=data.get("category", "other"),
            monthly_cost=Decimal(str(data.get("monthly_cost", 0))),
            original_price=Decimal(str(data["original_price"])) if data.get("original_price") else None,
            currency=data.get("currency", "USD"),
            billing_cycle=data.get("billing_cycle", "monthly"),
            billing_day=data.get("billing_day"),
            next_billing_date=self._parse_date(data.get("next_billing_date")),
            trial_ends_at=self._parse_datetime(data.get("trial_ends_at")),
            status=data.get("status", "active"),
            auto_renew=data.get("auto_renew", True),
            alert_days_before=data.get("alert_days_before", 3),
            alert_enabled=data.get("alert_enabled", True),
            last_alert_sent_at=self._parse_datetime(data.get("last_alert_sent_at")),
            notes=data.get("notes"),
            api_key_configured=data.get("api_key_configured", False),
            external_subscription_id=data.get("external_subscription_id"),
            external_customer_id=data.get("external_customer_id"),
            created_at=self._parse_datetime(data["created_at"]) or datetime.now(timezone.utc),
            updated_at=self._parse_datetime(data.get("updated_at"))
        )

    def _map_usage_to_response(self, data: Dict[str, Any]) -> SubscriptionUsageResponse:
        """Map usage row to response model."""
        return SubscriptionUsageResponse(
            id=data["id"],
            subscription_id=data["subscription_id"],
            user_id=data["user_id"],
            period_start=self._parse_date(data["period_start"]),
            period_end=self._parse_date(data["period_end"]),
            usage_amount=Decimal(str(data.get("usage_amount", 0))),
            usage_unit=data.get("usage_unit", "tokens"),
            cost_usd=Decimal(str(data.get("cost_usd", 0))),
            breakdown=data.get("breakdown"),
            created_at=self._parse_datetime(data["created_at"]) or datetime.now(timezone.utc)
        )

    def _map_alert_to_response(self, data: Dict[str, Any]) -> SubscriptionAlertResponse:
        """Map alert row to response model."""
        return SubscriptionAlertResponse(
            id=data["id"],
            subscription_id=data["subscription_id"],
            user_id=data["user_id"],
            alert_type=data["alert_type"],
            message=data.get("message"),
            sent_at=self._parse_datetime(data["sent_at"]) or datetime.now(timezone.utc),
            channels=data.get("channels", []),
            delivery_status=data.get("delivery_status", "sent"),
            billing_date=self._parse_date(data.get("billing_date")),
            amount=Decimal(str(data["amount"])) if data.get("amount") else None
        )

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        """Parse datetime from string or return as-is."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                # Handle ISO format with timezone
                if value.endswith("Z"):
                    value = value[:-1] + "+00:00"
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None

    def _parse_date(self, value: Any) -> Optional[date]:
        """Parse date from string or return as-is."""
        if value is None:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            try:
                return datetime.strptime(value.split("T")[0], "%Y-%m-%d").date()
            except ValueError:
                return None
        return None


# =============================================================================
# Singleton Pattern
# =============================================================================

_subscription_service: Optional[SubscriptionService] = None


def get_subscription_service() -> SubscriptionService:
    """Get the subscription service instance."""
    global _subscription_service
    if _subscription_service is None:
        _subscription_service = SubscriptionService()
    return _subscription_service
