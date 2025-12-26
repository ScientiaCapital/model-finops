"""
Stripe Client Wrapper

Async wrapper for Stripe API operations with proper error handling
and type safety.

Usage:
    from app.billing import StripeClient

    stripe_client = StripeClient()

    # Create checkout session
    session = await stripe_client.create_checkout_session(
        customer_id="cus_xxx",
        price_id="price_xxx",
        success_url="https://app.example.com/success",
        cancel_url="https://app.example.com/cancel",
    )
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from functools import wraps
import asyncio

import stripe
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic Models for Stripe Responses
# =============================================================================

class StripeCustomer(BaseModel):
    """Stripe customer representation."""
    id: str
    email: Optional[str] = None
    name: Optional[str] = None
    default_payment_method: Optional[str] = None
    metadata: Dict[str, str] = Field(default_factory=dict)
    created: int


class StripeSubscription(BaseModel):
    """Stripe subscription representation."""
    id: str
    customer: str
    status: str
    current_period_start: int
    current_period_end: int
    cancel_at_period_end: bool = False
    canceled_at: Optional[int] = None
    trial_start: Optional[int] = None
    trial_end: Optional[int] = None
    items: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, str] = Field(default_factory=dict)


class StripeCheckoutSession(BaseModel):
    """Stripe checkout session representation."""
    id: str
    url: str
    customer: Optional[str] = None
    subscription: Optional[str] = None
    status: str
    mode: str
    success_url: str
    cancel_url: str


class StripeBillingPortalSession(BaseModel):
    """Stripe billing portal session representation."""
    id: str
    url: str
    customer: str
    return_url: str


class StripeInvoice(BaseModel):
    """Stripe invoice representation."""
    id: str
    customer: str
    subscription: Optional[str] = None
    status: str
    total: int
    amount_paid: int
    amount_due: int
    currency: str
    hosted_invoice_url: Optional[str] = None
    invoice_pdf: Optional[str] = None
    created: int
    due_date: Optional[int] = None
    paid_at: Optional[int] = None


class StripePrice(BaseModel):
    """Stripe price representation."""
    id: str
    product: str
    unit_amount: Optional[int] = None
    currency: str
    recurring: Optional[Dict[str, Any]] = None
    metadata: Dict[str, str] = Field(default_factory=dict)


class StripeWebhookEvent(BaseModel):
    """Stripe webhook event representation."""
    id: str
    type: str
    data: Dict[str, Any]
    created: int


# =============================================================================
# Stripe Error Classes
# =============================================================================

class StripeClientError(Exception):
    """Base exception for Stripe client errors."""
    def __init__(self, message: str, stripe_code: Optional[str] = None):
        self.message = message
        self.stripe_code = stripe_code
        super().__init__(message)


class StripeAuthenticationError(StripeClientError):
    """Raised when Stripe authentication fails."""
    pass


class StripeInvalidRequestError(StripeClientError):
    """Raised when request parameters are invalid."""
    pass


class StripeCardError(StripeClientError):
    """Raised when a card error occurs."""
    pass


class StripeRateLimitError(StripeClientError):
    """Raised when rate limit is exceeded."""
    pass


# =============================================================================
# Async Wrapper Decorator
# =============================================================================

def async_stripe_call(func):
    """
    Decorator to run synchronous Stripe API calls in a thread pool.

    Stripe's Python SDK is synchronous, so we run it in an executor
    to avoid blocking the async event loop.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
    return wrapper


# =============================================================================
# Stripe Client
# =============================================================================

class StripeClient:
    """
    Async wrapper for Stripe API operations.

    Provides type-safe methods for common Stripe operations with
    proper error handling and logging.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Stripe client.

        Args:
            api_key: Stripe secret key. If not provided, uses STRIPE_SECRET_KEY env var.
        """
        import os

        self.api_key = api_key or os.getenv("STRIPE_SECRET_KEY")
        if not self.api_key:
            raise ValueError("STRIPE_SECRET_KEY environment variable not set")

        stripe.api_key = self.api_key
        stripe.api_version = "2024-12-18.acacia"  # Lock API version

        logger.info("Stripe client initialized")

    # =========================================================================
    # Customer Management
    # =========================================================================

    async def create_customer(
        self,
        email: str,
        name: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> StripeCustomer:
        """
        Create a new Stripe customer.

        Args:
            email: Customer email address
            name: Customer name
            metadata: Additional metadata (e.g., user_id)

        Returns:
            Created customer object
        """
        try:
            customer = await self._create_customer_sync(
                email=email,
                name=name,
                metadata=metadata or {},
            )
            logger.info(f"Created Stripe customer: {customer.id}")
            return StripeCustomer(
                id=customer.id,
                email=customer.email,
                name=customer.name,
                default_payment_method=customer.invoice_settings.default_payment_method
                if customer.invoice_settings else None,
                metadata=dict(customer.metadata or {}),
                created=customer.created,
            )
        except stripe.error.StripeError as e:
            self._handle_stripe_error(e)

    @async_stripe_call
    def _create_customer_sync(
        self, email: str, name: Optional[str], metadata: Dict[str, str]
    ):
        return stripe.Customer.create(
            email=email,
            name=name,
            metadata=metadata,
        )

    async def get_customer(self, customer_id: str) -> Optional[StripeCustomer]:
        """
        Retrieve a Stripe customer by ID.

        Args:
            customer_id: Stripe customer ID

        Returns:
            Customer object or None if not found
        """
        try:
            customer = await self._get_customer_sync(customer_id)
            return StripeCustomer(
                id=customer.id,
                email=customer.email,
                name=customer.name,
                default_payment_method=customer.invoice_settings.default_payment_method
                if customer.invoice_settings else None,
                metadata=dict(customer.metadata or {}),
                created=customer.created,
            )
        except stripe.error.InvalidRequestError:
            return None
        except stripe.error.StripeError as e:
            self._handle_stripe_error(e)

    @async_stripe_call
    def _get_customer_sync(self, customer_id: str):
        return stripe.Customer.retrieve(customer_id)

    async def update_customer(
        self,
        customer_id: str,
        email: Optional[str] = None,
        name: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> StripeCustomer:
        """
        Update a Stripe customer.

        Args:
            customer_id: Stripe customer ID
            email: New email address
            name: New name
            metadata: Updated metadata

        Returns:
            Updated customer object
        """
        try:
            params = {}
            if email is not None:
                params["email"] = email
            if name is not None:
                params["name"] = name
            if metadata is not None:
                params["metadata"] = metadata

            customer = await self._update_customer_sync(customer_id, params)
            logger.info(f"Updated Stripe customer: {customer_id}")
            return StripeCustomer(
                id=customer.id,
                email=customer.email,
                name=customer.name,
                default_payment_method=customer.invoice_settings.default_payment_method
                if customer.invoice_settings else None,
                metadata=dict(customer.metadata or {}),
                created=customer.created,
            )
        except stripe.error.StripeError as e:
            self._handle_stripe_error(e)

    @async_stripe_call
    def _update_customer_sync(self, customer_id: str, params: Dict[str, Any]):
        return stripe.Customer.modify(customer_id, **params)

    # =========================================================================
    # Subscription Management
    # =========================================================================

    async def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        trial_days: Optional[int] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> StripeSubscription:
        """
        Create a new subscription for a customer.

        Args:
            customer_id: Stripe customer ID
            price_id: Stripe price ID
            trial_days: Number of trial days
            metadata: Additional metadata

        Returns:
            Created subscription object
        """
        try:
            subscription = await self._create_subscription_sync(
                customer_id=customer_id,
                price_id=price_id,
                trial_days=trial_days,
                metadata=metadata or {},
            )
            logger.info(f"Created subscription: {subscription.id}")
            return self._parse_subscription(subscription)
        except stripe.error.StripeError as e:
            self._handle_stripe_error(e)

    @async_stripe_call
    def _create_subscription_sync(
        self,
        customer_id: str,
        price_id: str,
        trial_days: Optional[int],
        metadata: Dict[str, str],
    ):
        params = {
            "customer": customer_id,
            "items": [{"price": price_id}],
            "metadata": metadata,
        }
        if trial_days:
            params["trial_period_days"] = trial_days
        return stripe.Subscription.create(**params)

    async def get_subscription(self, subscription_id: str) -> Optional[StripeSubscription]:
        """
        Retrieve a subscription by ID.

        Args:
            subscription_id: Stripe subscription ID

        Returns:
            Subscription object or None if not found
        """
        try:
            subscription = await self._get_subscription_sync(subscription_id)
            return self._parse_subscription(subscription)
        except stripe.error.InvalidRequestError:
            return None
        except stripe.error.StripeError as e:
            self._handle_stripe_error(e)

    @async_stripe_call
    def _get_subscription_sync(self, subscription_id: str):
        return stripe.Subscription.retrieve(subscription_id)

    async def cancel_subscription(
        self,
        subscription_id: str,
        at_period_end: bool = True,
    ) -> StripeSubscription:
        """
        Cancel a subscription.

        Args:
            subscription_id: Stripe subscription ID
            at_period_end: If True, cancel at end of billing period

        Returns:
            Updated subscription object
        """
        try:
            if at_period_end:
                subscription = await self._update_subscription_sync(
                    subscription_id,
                    {"cancel_at_period_end": True},
                )
            else:
                subscription = await self._cancel_subscription_sync(subscription_id)

            logger.info(f"Canceled subscription: {subscription_id} (at_period_end={at_period_end})")
            return self._parse_subscription(subscription)
        except stripe.error.StripeError as e:
            self._handle_stripe_error(e)

    @async_stripe_call
    def _update_subscription_sync(self, subscription_id: str, params: Dict[str, Any]):
        return stripe.Subscription.modify(subscription_id, **params)

    @async_stripe_call
    def _cancel_subscription_sync(self, subscription_id: str):
        return stripe.Subscription.cancel(subscription_id)

    async def update_subscription(
        self,
        subscription_id: str,
        price_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> StripeSubscription:
        """
        Update a subscription (e.g., change plan).

        Args:
            subscription_id: Stripe subscription ID
            price_id: New price ID for plan change
            metadata: Updated metadata

        Returns:
            Updated subscription object
        """
        try:
            params = {}
            if metadata is not None:
                params["metadata"] = metadata

            # For price change, we need to update the subscription item
            if price_id:
                sub = await self._get_subscription_sync(subscription_id)
                item_id = sub["items"]["data"][0]["id"]
                params["items"] = [{"id": item_id, "price": price_id}]
                params["proration_behavior"] = "create_prorations"

            subscription = await self._update_subscription_sync(subscription_id, params)
            logger.info(f"Updated subscription: {subscription_id}")
            return self._parse_subscription(subscription)
        except stripe.error.StripeError as e:
            self._handle_stripe_error(e)

    def _parse_subscription(self, sub) -> StripeSubscription:
        """Parse Stripe subscription object to Pydantic model."""
        return StripeSubscription(
            id=sub.id,
            customer=sub.customer if isinstance(sub.customer, str) else sub.customer.id,
            status=sub.status,
            current_period_start=sub.current_period_start,
            current_period_end=sub.current_period_end,
            cancel_at_period_end=sub.cancel_at_period_end,
            canceled_at=sub.canceled_at,
            trial_start=sub.trial_start,
            trial_end=sub.trial_end,
            items=[{"price_id": item.price.id, "quantity": item.quantity} for item in sub["items"]["data"]],
            metadata=dict(sub.metadata or {}),
        )

    # =========================================================================
    # Checkout Sessions
    # =========================================================================

    async def create_checkout_session(
        self,
        price_id: str,
        success_url: str,
        cancel_url: str,
        customer_id: Optional[str] = None,
        customer_email: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        trial_days: Optional[int] = None,
        allow_promotion_codes: bool = True,
    ) -> StripeCheckoutSession:
        """
        Create a Stripe Checkout session for subscription purchase.

        Args:
            price_id: Stripe price ID for the subscription
            success_url: URL to redirect after successful checkout
            cancel_url: URL to redirect if checkout is canceled
            customer_id: Existing Stripe customer ID (optional)
            customer_email: Pre-fill email for new customers
            metadata: Additional metadata
            trial_days: Free trial period
            allow_promotion_codes: Allow promo codes

        Returns:
            Checkout session with URL
        """
        try:
            session = await self._create_checkout_session_sync(
                price_id=price_id,
                success_url=success_url,
                cancel_url=cancel_url,
                customer_id=customer_id,
                customer_email=customer_email,
                metadata=metadata or {},
                trial_days=trial_days,
                allow_promotion_codes=allow_promotion_codes,
            )
            logger.info(f"Created checkout session: {session.id}")
            return StripeCheckoutSession(
                id=session.id,
                url=session.url,
                customer=session.customer,
                subscription=session.subscription,
                status=session.status,
                mode=session.mode,
                success_url=session.success_url,
                cancel_url=session.cancel_url,
            )
        except stripe.error.StripeError as e:
            self._handle_stripe_error(e)

    @async_stripe_call
    def _create_checkout_session_sync(
        self,
        price_id: str,
        success_url: str,
        cancel_url: str,
        customer_id: Optional[str],
        customer_email: Optional[str],
        metadata: Dict[str, str],
        trial_days: Optional[int],
        allow_promotion_codes: bool,
    ):
        params = {
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": metadata,
            "allow_promotion_codes": allow_promotion_codes,
        }

        if customer_id:
            params["customer"] = customer_id
        elif customer_email:
            params["customer_email"] = customer_email

        if trial_days:
            params["subscription_data"] = {"trial_period_days": trial_days}

        return stripe.checkout.Session.create(**params)

    # =========================================================================
    # Billing Portal
    # =========================================================================

    async def create_portal_session(
        self,
        customer_id: str,
        return_url: str,
    ) -> StripeBillingPortalSession:
        """
        Create a billing portal session for self-service management.

        Args:
            customer_id: Stripe customer ID
            return_url: URL to redirect after portal session

        Returns:
            Portal session with URL
        """
        try:
            session = await self._create_portal_session_sync(
                customer_id=customer_id,
                return_url=return_url,
            )
            logger.info(f"Created portal session for customer: {customer_id}")
            return StripeBillingPortalSession(
                id=session.id,
                url=session.url,
                customer=session.customer,
                return_url=session.return_url,
            )
        except stripe.error.StripeError as e:
            self._handle_stripe_error(e)

    @async_stripe_call
    def _create_portal_session_sync(self, customer_id: str, return_url: str):
        return stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )

    # =========================================================================
    # Invoices
    # =========================================================================

    async def list_invoices(
        self,
        customer_id: str,
        limit: int = 10,
    ) -> List[StripeInvoice]:
        """
        List invoices for a customer.

        Args:
            customer_id: Stripe customer ID
            limit: Maximum number of invoices to return

        Returns:
            List of invoice objects
        """
        try:
            invoices = await self._list_invoices_sync(customer_id, limit)
            return [
                StripeInvoice(
                    id=inv.id,
                    customer=inv.customer,
                    subscription=inv.subscription,
                    status=inv.status,
                    total=inv.total,
                    amount_paid=inv.amount_paid,
                    amount_due=inv.amount_due,
                    currency=inv.currency,
                    hosted_invoice_url=inv.hosted_invoice_url,
                    invoice_pdf=inv.invoice_pdf,
                    created=inv.created,
                    due_date=inv.due_date,
                    paid_at=inv.status_transitions.paid_at if inv.status_transitions else None,
                )
                for inv in invoices.data
            ]
        except stripe.error.StripeError as e:
            self._handle_stripe_error(e)

    @async_stripe_call
    def _list_invoices_sync(self, customer_id: str, limit: int):
        return stripe.Invoice.list(customer=customer_id, limit=limit)

    async def get_upcoming_invoice(self, customer_id: str) -> Optional[StripeInvoice]:
        """
        Get the upcoming invoice for a customer.

        Args:
            customer_id: Stripe customer ID

        Returns:
            Upcoming invoice or None if no subscription
        """
        try:
            invoice = await self._get_upcoming_invoice_sync(customer_id)
            return StripeInvoice(
                id=invoice.id or "upcoming",
                customer=customer_id,
                subscription=invoice.subscription,
                status="upcoming",
                total=invoice.total,
                amount_paid=0,
                amount_due=invoice.amount_due,
                currency=invoice.currency,
                created=int(datetime.now().timestamp()),
            )
        except stripe.error.InvalidRequestError:
            return None
        except stripe.error.StripeError as e:
            self._handle_stripe_error(e)

    @async_stripe_call
    def _get_upcoming_invoice_sync(self, customer_id: str):
        return stripe.Invoice.upcoming(customer=customer_id)

    # =========================================================================
    # Prices
    # =========================================================================

    async def get_price(self, price_id: str) -> Optional[StripePrice]:
        """
        Retrieve a price by ID.

        Args:
            price_id: Stripe price ID

        Returns:
            Price object or None if not found
        """
        try:
            price = await self._get_price_sync(price_id)
            return StripePrice(
                id=price.id,
                product=price.product if isinstance(price.product, str) else price.product.id,
                unit_amount=price.unit_amount,
                currency=price.currency,
                recurring=dict(price.recurring) if price.recurring else None,
                metadata=dict(price.metadata or {}),
            )
        except stripe.error.InvalidRequestError:
            return None
        except stripe.error.StripeError as e:
            self._handle_stripe_error(e)

    @async_stripe_call
    def _get_price_sync(self, price_id: str):
        return stripe.Price.retrieve(price_id)

    # =========================================================================
    # Webhook Handling
    # =========================================================================

    def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str,
        webhook_secret: str,
    ) -> StripeWebhookEvent:
        """
        Verify and parse a Stripe webhook event.

        Args:
            payload: Raw request body bytes
            signature: Stripe-Signature header value
            webhook_secret: Webhook endpoint secret

        Returns:
            Verified webhook event

        Raises:
            StripeClientError: If signature verification fails
        """
        try:
            event = stripe.Webhook.construct_event(
                payload,
                signature,
                webhook_secret,
            )
            return StripeWebhookEvent(
                id=event.id,
                type=event.type,
                data=dict(event.data),
                created=event.created,
            )
        except stripe.error.SignatureVerificationError as e:
            raise StripeClientError(f"Webhook signature verification failed: {e}")
        except Exception as e:
            raise StripeClientError(f"Webhook parsing failed: {e}")

    # =========================================================================
    # Error Handling
    # =========================================================================

    def _handle_stripe_error(self, error: stripe.error.StripeError):
        """Convert Stripe errors to typed exceptions."""
        if isinstance(error, stripe.error.AuthenticationError):
            logger.error(f"Stripe authentication error: {error}")
            raise StripeAuthenticationError(str(error))
        elif isinstance(error, stripe.error.InvalidRequestError):
            logger.warning(f"Stripe invalid request: {error}")
            raise StripeInvalidRequestError(str(error), error.code)
        elif isinstance(error, stripe.error.CardError):
            logger.warning(f"Stripe card error: {error}")
            raise StripeCardError(str(error), error.code)
        elif isinstance(error, stripe.error.RateLimitError):
            logger.warning(f"Stripe rate limit: {error}")
            raise StripeRateLimitError(str(error))
        else:
            logger.error(f"Stripe error: {error}")
            raise StripeClientError(str(error))
