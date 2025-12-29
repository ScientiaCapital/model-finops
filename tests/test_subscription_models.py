"""
Tests for Subscription Tracking Pydantic Models

Test model validation, computed fields, and enum handling.
"""

import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal
from pydantic import ValidationError


class TestSubscriptionStatusEnum:
    """Test SubscriptionStatus enum values."""

    def test_active_status(self):
        from app.models.subscription import SubscriptionStatus
        assert SubscriptionStatus.ACTIVE.value == "active"

    def test_trial_status(self):
        from app.models.subscription import SubscriptionStatus
        assert SubscriptionStatus.TRIAL.value == "trial"

    def test_cancelled_status(self):
        from app.models.subscription import SubscriptionStatus
        assert SubscriptionStatus.CANCELLED.value == "cancelled"

    def test_paused_status(self):
        from app.models.subscription import SubscriptionStatus
        assert SubscriptionStatus.PAUSED.value == "paused"

    def test_past_due_status(self):
        from app.models.subscription import SubscriptionStatus
        assert SubscriptionStatus.PAST_DUE.value == "past_due"


class TestBillingCycleEnum:
    """Test BillingCycle enum values."""

    def test_monthly_cycle(self):
        from app.models.subscription import BillingCycle
        assert BillingCycle.MONTHLY.value == "monthly"

    def test_yearly_cycle(self):
        from app.models.subscription import BillingCycle
        assert BillingCycle.YEARLY.value == "yearly"

    def test_quarterly_cycle(self):
        from app.models.subscription import BillingCycle
        assert BillingCycle.QUARTERLY.value == "quarterly"

    def test_weekly_cycle(self):
        from app.models.subscription import BillingCycle
        assert BillingCycle.WEEKLY.value == "weekly"

    def test_one_time_cycle(self):
        from app.models.subscription import BillingCycle
        assert BillingCycle.ONE_TIME.value == "one_time"

    def test_usage_based_cycle(self):
        from app.models.subscription import BillingCycle
        assert BillingCycle.USAGE_BASED.value == "usage_based"


class TestServiceCategoryEnum:
    """Test ServiceCategory enum values."""

    def test_llm_provider_category(self):
        from app.models.subscription import ServiceCategory
        assert ServiceCategory.LLM_PROVIDER.value == "llm_provider"

    def test_voice_tts_category(self):
        from app.models.subscription import ServiceCategory
        assert ServiceCategory.VOICE_TTS.value == "voice_tts"

    def test_voice_stt_category(self):
        from app.models.subscription import ServiceCategory
        assert ServiceCategory.VOICE_STT.value == "voice_stt"

    def test_infrastructure_category(self):
        from app.models.subscription import ServiceCategory
        assert ServiceCategory.INFRASTRUCTURE.value == "infrastructure"

    def test_ai_media_category(self):
        from app.models.subscription import ServiceCategory
        assert ServiceCategory.AI_MEDIA.value == "ai_media"

    def test_observability_category(self):
        from app.models.subscription import ServiceCategory
        assert ServiceCategory.OBSERVABILITY.value == "observability"

    def test_billing_category(self):
        from app.models.subscription import ServiceCategory
        assert ServiceCategory.BILLING.value == "billing"

    def test_other_category(self):
        from app.models.subscription import ServiceCategory
        assert ServiceCategory.OTHER.value == "other"


class TestSubscriptionCreate:
    """Test SubscriptionCreate model validation."""

    def test_minimal_subscription(self):
        from app.models.subscription import SubscriptionCreate
        sub = SubscriptionCreate(service_name="Anthropic")
        assert sub.service_name == "Anthropic"
        assert sub.monthly_cost == Decimal("0.00")
        assert sub.currency == "USD"

    def test_full_subscription(self):
        from app.models.subscription import (
            SubscriptionCreate, SubscriptionStatus,
            BillingCycle, ServiceCategory
        )
        sub = SubscriptionCreate(
            service_name="Anthropic Claude",
            service_provider="anthropic",
            category=ServiceCategory.LLM_PROVIDER,
            monthly_cost=Decimal("50.00"),
            original_price=Decimal("600.00"),
            billing_cycle=BillingCycle.YEARLY,
            billing_day=15,
            status=SubscriptionStatus.ACTIVE,
            alert_days_before=7,
            notes="API key: sk-ant-***"
        )
        assert sub.service_name == "Anthropic Claude"
        assert sub.category == ServiceCategory.LLM_PROVIDER
        assert sub.monthly_cost == Decimal("50.00")
        assert sub.billing_cycle == BillingCycle.YEARLY
        assert sub.billing_day == 15

    def test_service_name_required(self):
        from app.models.subscription import SubscriptionCreate
        with pytest.raises(ValidationError):
            SubscriptionCreate()

    def test_service_name_min_length(self):
        from app.models.subscription import SubscriptionCreate
        with pytest.raises(ValidationError):
            SubscriptionCreate(service_name="")

    def test_billing_day_range(self):
        from app.models.subscription import SubscriptionCreate
        # Valid billing day
        sub = SubscriptionCreate(service_name="Test", billing_day=31)
        assert sub.billing_day == 31

        # Invalid billing day (too high)
        with pytest.raises(ValidationError):
            SubscriptionCreate(service_name="Test", billing_day=32)

        # Invalid billing day (too low)
        with pytest.raises(ValidationError):
            SubscriptionCreate(service_name="Test", billing_day=0)

    def test_monthly_cost_non_negative(self):
        from app.models.subscription import SubscriptionCreate
        with pytest.raises(ValidationError):
            SubscriptionCreate(service_name="Test", monthly_cost=Decimal("-10.00"))

    def test_alert_days_before_range(self):
        from app.models.subscription import SubscriptionCreate
        # Valid alert days
        sub = SubscriptionCreate(service_name="Test", alert_days_before=30)
        assert sub.alert_days_before == 30

        # Invalid (too high)
        with pytest.raises(ValidationError):
            SubscriptionCreate(service_name="Test", alert_days_before=31)

    def test_string_to_enum_conversion(self):
        """Test that string values are converted to enums."""
        from app.models.subscription import SubscriptionCreate, BillingCycle
        sub = SubscriptionCreate(
            service_name="Test",
            billing_cycle="yearly",
            category="llm_provider",
            status="active"
        )
        assert sub.billing_cycle == BillingCycle.YEARLY


class TestSubscriptionUpdate:
    """Test SubscriptionUpdate model validation."""

    def test_empty_update(self):
        from app.models.subscription import SubscriptionUpdate
        update = SubscriptionUpdate()
        assert update.service_name is None
        assert update.monthly_cost is None

    def test_partial_update(self):
        from app.models.subscription import SubscriptionUpdate
        update = SubscriptionUpdate(
            monthly_cost=Decimal("99.00"),
            notes="Updated price"
        )
        assert update.monthly_cost == Decimal("99.00")
        assert update.notes == "Updated price"
        assert update.service_name is None

    def test_status_update(self):
        from app.models.subscription import SubscriptionUpdate, SubscriptionStatus
        update = SubscriptionUpdate(status=SubscriptionStatus.CANCELLED)
        assert update.status == SubscriptionStatus.CANCELLED


class TestSubscriptionResponse:
    """Test SubscriptionResponse model with computed fields."""

    def test_yearly_cost_computed(self):
        from app.models.subscription import SubscriptionResponse
        sub = SubscriptionResponse(
            id="uuid-1",
            user_id="user-1",
            service_name="Anthropic",
            category="llm_provider",
            monthly_cost=Decimal("50.00"),
            currency="USD",
            billing_cycle="monthly",
            status="active",
            auto_renew=True,
            alert_days_before=3,
            alert_enabled=True,
            api_key_configured=True,
            created_at=datetime.now()
        )
        assert sub.yearly_cost == Decimal("600.00")

    def test_is_trial_computed(self):
        from app.models.subscription import SubscriptionResponse
        # Trial subscription
        trial_sub = SubscriptionResponse(
            id="uuid-1",
            user_id="user-1",
            service_name="Test",
            category="other",
            monthly_cost=Decimal("0.00"),
            currency="USD",
            billing_cycle="monthly",
            status="trial",
            auto_renew=True,
            alert_days_before=3,
            alert_enabled=True,
            api_key_configured=False,
            created_at=datetime.now()
        )
        assert trial_sub.is_trial is True

        # Active subscription
        active_sub = SubscriptionResponse(
            id="uuid-2",
            user_id="user-1",
            service_name="Test2",
            category="other",
            monthly_cost=Decimal("10.00"),
            currency="USD",
            billing_cycle="monthly",
            status="active",
            auto_renew=True,
            alert_days_before=3,
            alert_enabled=True,
            api_key_configured=True,
            created_at=datetime.now()
        )
        assert active_sub.is_trial is False


class TestSubscriptionListResponse:
    """Test SubscriptionListResponse with computed fields."""

    def test_total_monthly_cost_computed(self):
        from app.models.subscription import SubscriptionResponse, SubscriptionListResponse
        now = datetime.now()
        subs = [
            SubscriptionResponse(
                id="uuid-1", user_id="user-1", service_name="A",
                category="llm_provider", monthly_cost=Decimal("50.00"),
                currency="USD", billing_cycle="monthly", status="active",
                auto_renew=True, alert_days_before=3, alert_enabled=True,
                api_key_configured=True, created_at=now
            ),
            SubscriptionResponse(
                id="uuid-2", user_id="user-1", service_name="B",
                category="infrastructure", monthly_cost=Decimal("20.00"),
                currency="USD", billing_cycle="monthly", status="active",
                auto_renew=True, alert_days_before=3, alert_enabled=True,
                api_key_configured=False, created_at=now
            ),
        ]
        response = SubscriptionListResponse(subscriptions=subs, total=2)
        assert response.total_monthly_cost == Decimal("70.00")

    def test_empty_list(self):
        from app.models.subscription import SubscriptionListResponse
        response = SubscriptionListResponse(subscriptions=[], total=0)
        assert response.total_monthly_cost == Decimal("0")


class TestSubscriptionUsageCreate:
    """Test SubscriptionUsageCreate validation."""

    def test_valid_usage(self):
        from app.models.subscription import SubscriptionUsageCreate
        usage = SubscriptionUsageCreate(
            period_start=date(2024, 12, 1),
            period_end=date(2024, 12, 31),
            usage_amount=Decimal("1000000"),
            usage_unit="tokens",
            cost_usd=Decimal("15.50")
        )
        assert usage.usage_amount == Decimal("1000000")

    def test_period_end_after_start(self):
        from app.models.subscription import SubscriptionUsageCreate
        with pytest.raises(ValidationError):
            SubscriptionUsageCreate(
                period_start=date(2024, 12, 31),
                period_end=date(2024, 12, 1),
                usage_amount=Decimal("100")
            )

    def test_negative_usage_rejected(self):
        from app.models.subscription import SubscriptionUsageCreate
        with pytest.raises(ValidationError):
            SubscriptionUsageCreate(
                period_start=date(2024, 12, 1),
                period_end=date(2024, 12, 31),
                usage_amount=Decimal("-100")
            )


class TestUpcomingBillingAlert:
    """Test UpcomingBillingAlert with urgency computation."""

    def test_critical_urgency(self):
        from app.models.subscription import UpcomingBillingAlert
        alert = UpcomingBillingAlert(
            subscription_id="uuid-1",
            user_id="user-1",
            service_name="Anthropic",
            monthly_cost=Decimal("50.00"),
            next_billing_date=date.today() + timedelta(days=1),
            days_until_billing=1,
            alert_days_before=3
        )
        assert alert.urgency == "critical"

    def test_high_urgency(self):
        from app.models.subscription import UpcomingBillingAlert
        alert = UpcomingBillingAlert(
            subscription_id="uuid-1",
            user_id="user-1",
            service_name="Anthropic",
            monthly_cost=Decimal("50.00"),
            next_billing_date=date.today() + timedelta(days=2),
            days_until_billing=2,
            alert_days_before=3
        )
        assert alert.urgency == "high"

    def test_medium_urgency(self):
        from app.models.subscription import UpcomingBillingAlert
        alert = UpcomingBillingAlert(
            subscription_id="uuid-1",
            user_id="user-1",
            service_name="Anthropic",
            monthly_cost=Decimal("50.00"),
            next_billing_date=date.today() + timedelta(days=5),
            days_until_billing=5,
            alert_days_before=7
        )
        assert alert.urgency == "medium"

    def test_low_urgency(self):
        from app.models.subscription import UpcomingBillingAlert
        alert = UpcomingBillingAlert(
            subscription_id="uuid-1",
            user_id="user-1",
            service_name="Anthropic",
            monthly_cost=Decimal("50.00"),
            next_billing_date=date.today() + timedelta(days=10),
            days_until_billing=10,
            alert_days_before=7
        )
        assert alert.urgency == "low"


class TestSpendSummary:
    """Test SpendSummary with computed fields."""

    def test_average_per_subscription(self):
        from app.models.subscription import SpendSummary
        summary = SpendSummary(
            total_monthly_cost=Decimal("300.00"),
            total_yearly_cost=Decimal("3600.00"),
            active_subscriptions=6,
            by_category={"llm_provider": Decimal("200.00"), "infrastructure": Decimal("100.00")}
        )
        assert summary.average_per_subscription == Decimal("50.00")

    def test_average_with_zero_subscriptions(self):
        from app.models.subscription import SpendSummary
        summary = SpendSummary(
            total_monthly_cost=Decimal("0.00"),
            total_yearly_cost=Decimal("0.00"),
            active_subscriptions=0,
            by_category={}
        )
        assert summary.average_per_subscription == Decimal("0.00")

    def test_top_category(self):
        from app.models.subscription import SpendSummary
        summary = SpendSummary(
            total_monthly_cost=Decimal("300.00"),
            total_yearly_cost=Decimal("3600.00"),
            active_subscriptions=6,
            by_category={
                "llm_provider": Decimal("200.00"),
                "infrastructure": Decimal("50.00"),
                "voice_tts": Decimal("50.00")
            }
        )
        assert summary.top_category == "llm_provider"

    def test_top_category_empty(self):
        from app.models.subscription import SpendSummary
        summary = SpendSummary(
            total_monthly_cost=Decimal("0.00"),
            total_yearly_cost=Decimal("0.00"),
            active_subscriptions=0,
            by_category={}
        )
        assert summary.top_category is None


class TestSubscriptionImport:
    """Test import models."""

    def test_import_row_minimal(self):
        from app.models.subscription import SubscriptionImportRow
        row = SubscriptionImportRow(
            service_name="Anthropic",
            monthly_cost=Decimal("50.00")
        )
        assert row.service_name == "Anthropic"
        assert row.billing_cycle == "monthly"
        assert row.category == "other"

    def test_import_row_full(self):
        from app.models.subscription import SubscriptionImportRow
        row = SubscriptionImportRow(
            service_name="Anthropic",
            monthly_cost=Decimal("50.00"),
            billing_cycle="yearly",
            category="llm_provider",
            billing_day=15,
            notes="API Key: sk-***"
        )
        assert row.billing_day == 15
        assert row.category == "llm_provider"

    def test_import_request(self):
        from app.models.subscription import (
            SubscriptionImportRequest, SubscriptionImportRow
        )
        rows = [
            SubscriptionImportRow(service_name="A", monthly_cost=Decimal("10.00")),
            SubscriptionImportRow(service_name="B", monthly_cost=Decimal("20.00")),
        ]
        request = SubscriptionImportRequest(subscriptions=rows)
        assert len(request.subscriptions) == 2
        assert request.skip_duplicates is True


class TestSubscriptionFilters:
    """Test filter model."""

    def test_empty_filters(self):
        from app.models.subscription import SubscriptionFilters
        filters = SubscriptionFilters()
        assert filters.category is None
        assert filters.status is None
        assert filters.search is None

    def test_partial_filters(self):
        from app.models.subscription import (
            SubscriptionFilters, ServiceCategory, SubscriptionStatus
        )
        filters = SubscriptionFilters(
            category=ServiceCategory.LLM_PROVIDER,
            status=SubscriptionStatus.ACTIVE,
            min_cost=Decimal("10.00")
        )
        assert filters.category == ServiceCategory.LLM_PROVIDER
        assert filters.status == SubscriptionStatus.ACTIVE
        assert filters.min_cost == Decimal("10.00")
