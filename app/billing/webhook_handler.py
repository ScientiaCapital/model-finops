"""
Stripe Webhook Handler

Processes incoming Stripe webhook events and updates the database accordingly.
Ensures idempotent processing using event IDs.

Key Events Handled:
- checkout.session.completed: New subscription via Checkout
- customer.subscription.created/updated/deleted: Subscription lifecycle
- invoice.paid: Record successful payments
- invoice.payment_failed: Mark subscription as past_due

Usage in FastAPI:
    from app.billing.webhook_handler import WebhookHandler

    @router.post("/webhook")
    async def stripe_webhook(request: Request):
        handler = WebhookHandler(stripe_client, billing_service, supabase_client)
        return await handler.handle_webhook(request)
"""

import logging
from typing import Optional, Dict, Any, TYPE_CHECKING
from datetime import datetime, timezone

from fastapi import Request, HTTPException
from pydantic import BaseModel

from app.billing.stripe_client import StripeClient, StripeWebhookEvent
from app.database.supabase_client import SupabaseClient

if TYPE_CHECKING:
    from app.services.billing_service import BillingService

logger = logging.getLogger(__name__)


# =============================================================================
# Models
# =============================================================================

class WebhookResult(BaseModel):
    """Result of webhook processing."""
    success: bool
    event_id: str
    event_type: str
    message: str
    processed_at: datetime


# =============================================================================
# Webhook Handler
# =============================================================================

class WebhookHandler:
    """
    Handles Stripe webhook events.

    Provides idempotent processing of Stripe events, updating the database
    and maintaining an audit log of all received events.
    """

    def __init__(
        self,
        stripe_client: StripeClient,
        billing_service: "BillingService",
        supabase_client: SupabaseClient,
        webhook_secret: Optional[str] = None,
    ):
        """
        Initialize webhook handler.

        Args:
            stripe_client: Configured Stripe client
            billing_service: Billing service instance
            supabase_client: Supabase client for event logging
            webhook_secret: Stripe webhook signing secret
        """
        import os

        self.stripe = stripe_client
        self.billing = billing_service
        self.db = supabase_client
        self.webhook_secret = webhook_secret or os.getenv("STRIPE_WEBHOOK_SECRET")

        if not self.webhook_secret:
            logger.warning("STRIPE_WEBHOOK_SECRET not set - webhook verification disabled!")

    async def handle_webhook(self, request: Request) -> WebhookResult:
        """
        Process an incoming Stripe webhook.

        Args:
            request: FastAPI Request object

        Returns:
            WebhookResult indicating success/failure

        Raises:
            HTTPException: If signature verification fails or processing errors
        """
        # Get raw body and signature
        payload = await request.body()
        signature = request.headers.get("Stripe-Signature")

        if not signature:
            raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

        # Verify and parse event
        try:
            event = self.stripe.verify_webhook_signature(
                payload=payload,
                signature=signature,
                webhook_secret=self.webhook_secret,
            )
        except Exception as e:
            logger.error(f"Webhook signature verification failed: {e}")
            raise HTTPException(status_code=400, detail=str(e))

        # Check for duplicate event (idempotency)
        if await self._is_event_processed(event.id):
            logger.info(f"Duplicate event ignored: {event.id}")
            return WebhookResult(
                success=True,
                event_id=event.id,
                event_type=event.type,
                message="Event already processed",
                processed_at=datetime.now(timezone.utc),
            )

        # Log event before processing
        await self._log_event(event, processed=False)

        # Process event based on type
        try:
            await self._process_event(event)

            # Mark event as processed
            await self._mark_event_processed(event.id)

            logger.info(f"Successfully processed webhook: {event.type} ({event.id})")
            return WebhookResult(
                success=True,
                event_id=event.id,
                event_type=event.type,
                message="Event processed successfully",
                processed_at=datetime.now(timezone.utc),
            )

        except Exception as e:
            logger.error(f"Error processing webhook {event.type}: {e}")
            await self._record_event_error(event.id, str(e))
            raise HTTPException(
                status_code=500,
                detail=f"Error processing event: {str(e)}",
            )

    async def _process_event(self, event: StripeWebhookEvent) -> None:
        """
        Route event to appropriate handler.

        Args:
            event: Verified Stripe webhook event
        """
        handlers = {
            "checkout.session.completed": self._handle_checkout_completed,
            "customer.created": self._handle_customer_created,
            "customer.updated": self._handle_customer_updated,
            "customer.subscription.created": self._handle_subscription_created,
            "customer.subscription.updated": self._handle_subscription_updated,
            "customer.subscription.deleted": self._handle_subscription_deleted,
            "invoice.paid": self._handle_invoice_paid,
            "invoice.payment_failed": self._handle_invoice_payment_failed,
        }

        handler = handlers.get(event.type)
        if handler:
            await handler(event)
        else:
            logger.debug(f"Unhandled event type: {event.type}")

    # =========================================================================
    # Checkout Events
    # =========================================================================

    async def _handle_checkout_completed(self, event: StripeWebhookEvent) -> None:
        """
        Handle successful checkout session.

        Creates or updates customer and subscription records.
        """
        session = event.data.get("object", {})

        # Only handle subscription mode
        if session.get("mode") != "subscription":
            logger.debug("Ignoring non-subscription checkout")
            return

        customer_id = session.get("customer")
        subscription_id = session.get("subscription")
        user_id = session.get("metadata", {}).get("supabase_user_id")

        if not user_id:
            logger.warning(f"Checkout session missing supabase_user_id: {session.get('id')}")
            return

        logger.info(f"Checkout completed for user {user_id[:8]}...")

        # Get full subscription details from Stripe
        if subscription_id:
            subscription = await self.stripe.get_subscription(subscription_id)
            if subscription:
                await self.billing.sync_subscription_from_stripe(subscription, user_id)

    # =========================================================================
    # Customer Events
    # =========================================================================

    async def _handle_customer_created(self, event: StripeWebhookEvent) -> None:
        """Handle customer creation (usually handled during checkout)."""
        customer = event.data.get("object", {})
        user_id = customer.get("metadata", {}).get("supabase_user_id")

        if not user_id:
            logger.debug("Customer created without supabase_user_id")
            return

        # Check if customer already exists in our database
        existing = await self.db.execute_query(
            "customers",
            "select",
            filters={"stripe_customer_id": customer.get("id")},
        )

        if not existing:
            await self.db.execute_query(
                "customers",
                "insert",
                data={
                    "user_id": user_id,
                    "stripe_customer_id": customer.get("id"),
                    "email": customer.get("email"),
                    "name": customer.get("name"),
                },
            )
            logger.info(f"Created customer record for {customer.get('id')}")

    async def _handle_customer_updated(self, event: StripeWebhookEvent) -> None:
        """Handle customer update (email, name, etc.)."""
        customer = event.data.get("object", {})
        stripe_customer_id = customer.get("id")

        await self.db.execute_query(
            "customers",
            "update",
            data={
                "email": customer.get("email"),
                "name": customer.get("name"),
            },
            filters={"stripe_customer_id": stripe_customer_id},
        )

        logger.info(f"Updated customer: {stripe_customer_id}")

    # =========================================================================
    # Subscription Events
    # =========================================================================

    async def _handle_subscription_created(self, event: StripeWebhookEvent) -> None:
        """Handle new subscription creation."""
        await self._sync_subscription(event)

    async def _handle_subscription_updated(self, event: StripeWebhookEvent) -> None:
        """Handle subscription updates (status change, plan change, etc.)."""
        await self._sync_subscription(event)

    async def _handle_subscription_deleted(self, event: StripeWebhookEvent) -> None:
        """Handle subscription cancellation/deletion."""
        subscription = event.data.get("object", {})
        stripe_subscription_id = subscription.get("id")

        # Update subscription status to canceled
        await self.db.execute_query(
            "subscriptions",
            "update",
            data={
                "status": "canceled",
                "canceled_at": datetime.now(timezone.utc).isoformat(),
            },
            filters={"stripe_subscription_id": stripe_subscription_id},
        )

        logger.info(f"Subscription deleted: {stripe_subscription_id}")

    async def _sync_subscription(self, event: StripeWebhookEvent) -> None:
        """
        Sync subscription data from webhook event.

        Args:
            event: Webhook event containing subscription object
        """
        subscription_data = event.data.get("object", {})
        stripe_subscription_id = subscription_data.get("id")
        stripe_customer_id = subscription_data.get("customer")

        # Get user_id from customer record
        customer = await self.db.execute_query(
            "customers",
            "select",
            filters={"stripe_customer_id": stripe_customer_id},
        )

        if not customer:
            logger.warning(f"No customer found for Stripe customer: {stripe_customer_id}")
            return

        user_id = customer[0]["user_id"]

        # Get full subscription from Stripe for accurate data
        stripe_sub = await self.stripe.get_subscription(stripe_subscription_id)
        if stripe_sub:
            await self.billing.sync_subscription_from_stripe(stripe_sub, user_id)

    # =========================================================================
    # Invoice Events
    # =========================================================================

    async def _handle_invoice_paid(self, event: StripeWebhookEvent) -> None:
        """Handle successful invoice payment."""
        invoice = event.data.get("object", {})
        stripe_invoice_id = invoice.get("id")
        stripe_customer_id = invoice.get("customer")
        stripe_subscription_id = invoice.get("subscription")

        # Get user from customer
        customer = await self.db.execute_query(
            "customers",
            "select",
            filters={"stripe_customer_id": stripe_customer_id},
        )

        if not customer:
            logger.warning(f"Invoice paid for unknown customer: {stripe_customer_id}")
            return

        user_id = customer[0]["user_id"]
        customer_id = customer[0]["id"]

        # Get subscription ID from our database
        subscription = None
        if stripe_subscription_id:
            sub_result = await self.db.execute_query(
                "subscriptions",
                "select",
                filters={"stripe_subscription_id": stripe_subscription_id},
            )
            if sub_result:
                subscription = sub_result[0]

        # Record invoice in our database
        await self.db.execute_query(
            "invoices",
            "upsert",
            data={
                "user_id": user_id,
                "customer_id": customer_id,
                "subscription_id": subscription["id"] if subscription else None,
                "stripe_invoice_id": stripe_invoice_id,
                "stripe_hosted_invoice_url": invoice.get("hosted_invoice_url"),
                "stripe_pdf_url": invoice.get("invoice_pdf"),
                "invoice_number": invoice.get("number"),
                "status": "paid",
                "subtotal_cents": invoice.get("subtotal", 0),
                "tax_cents": invoice.get("tax", 0),
                "total_cents": invoice.get("total", 0),
                "amount_paid_cents": invoice.get("amount_paid", 0),
                "amount_due_cents": 0,
                "currency": invoice.get("currency", "usd"),
                "period_start": datetime.fromtimestamp(
                    invoice.get("period_start", 0), tz=timezone.utc
                ).isoformat() if invoice.get("period_start") else None,
                "period_end": datetime.fromtimestamp(
                    invoice.get("period_end", 0), tz=timezone.utc
                ).isoformat() if invoice.get("period_end") else None,
                "paid_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        # Ensure subscription is marked active
        if stripe_subscription_id:
            await self.db.execute_query(
                "subscriptions",
                "update",
                data={"status": "active"},
                filters={"stripe_subscription_id": stripe_subscription_id},
            )

        logger.info(f"Invoice paid: {stripe_invoice_id}")

    async def _handle_invoice_payment_failed(self, event: StripeWebhookEvent) -> None:
        """Handle failed invoice payment."""
        invoice = event.data.get("object", {})
        stripe_subscription_id = invoice.get("subscription")

        if not stripe_subscription_id:
            return

        # Mark subscription as past_due
        await self.db.execute_query(
            "subscriptions",
            "update",
            data={"status": "past_due"},
            filters={"stripe_subscription_id": stripe_subscription_id},
        )

        logger.warning(f"Invoice payment failed for subscription: {stripe_subscription_id}")

    # =========================================================================
    # Event Logging & Idempotency
    # =========================================================================

    async def _is_event_processed(self, event_id: str) -> bool:
        """Check if event was already processed."""
        result = await self.db.execute_query(
            "billing_events",
            "select",
            filters={"stripe_event_id": event_id, "processed": True},
        )
        return len(result) > 0

    async def _log_event(
        self,
        event: StripeWebhookEvent,
        processed: bool = False,
    ) -> None:
        """Log event to billing_events table."""
        # Map string event type to enum (handle potential mismatches)
        event_type = event.type
        if event_type not in [
            "checkout.session.completed",
            "customer.created", "customer.updated", "customer.deleted",
            "customer.subscription.created", "customer.subscription.updated",
            "customer.subscription.deleted",
            "invoice.created", "invoice.paid", "invoice.payment_failed", "invoice.finalized",
            "payment_intent.succeeded", "payment_intent.payment_failed",
            "charge.succeeded", "charge.failed", "charge.refunded",
        ]:
            # Store as generic type for unrecognized events
            logger.debug(f"Unknown event type: {event_type}")
            return  # Skip logging for unrecognized types

        # Extract resource IDs from event data
        obj = event.data.get("object", {})

        try:
            await self.db.execute_query(
                "billing_events",
                "upsert",
                data={
                    "stripe_event_id": event.id,
                    "event_type": event_type,
                    "stripe_customer_id": obj.get("customer") if isinstance(obj.get("customer"), str) else None,
                    "stripe_subscription_id": obj.get("subscription") if isinstance(obj.get("subscription"), str) else None,
                    "stripe_invoice_id": obj.get("id") if "invoice" in event_type else None,
                    "payload": event.data,
                    "processed": processed,
                    "processed_at": datetime.now(timezone.utc).isoformat() if processed else None,
                },
            )
        except Exception as e:
            logger.error(f"Failed to log event: {e}")

    async def _mark_event_processed(self, event_id: str) -> None:
        """Mark event as successfully processed."""
        await self.db.execute_query(
            "billing_events",
            "update",
            data={
                "processed": True,
                "processed_at": datetime.now(timezone.utc).isoformat(),
            },
            filters={"stripe_event_id": event_id},
        )

    async def _record_event_error(self, event_id: str, error_message: str) -> None:
        """Record error for failed event processing."""
        # Get current retry count
        result = await self.db.execute_query(
            "billing_events",
            "select",
            filters={"stripe_event_id": event_id},
        )

        retry_count = 0
        if result:
            retry_count = result[0].get("retry_count", 0) + 1

        await self.db.execute_query(
            "billing_events",
            "update",
            data={
                "error_message": error_message,
                "retry_count": retry_count,
            },
            filters={"stripe_event_id": event_id},
        )
