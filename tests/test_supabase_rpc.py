"""Services call stored procedures through a real SupabaseClient wrapper.

Only the supabase-py client objects inside the wrapper are faked (the network boundary), so a
method missing from the wrapper fails here instead of being papered over by a MagicMock.
"""

import os
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.database.supabase_client import SupabaseClient
from app.services.enterprise_service import EnterpriseService
from app.services.subscription_service import SubscriptionService


def _fake_supabase_py(rows: list[dict]) -> MagicMock:
    """A stand-in for supabase.Client whose rpc().execute() returns `rows`."""
    fake = MagicMock(name="supabase.Client")
    fake.rpc.return_value.execute.return_value.data = rows
    return fake


@pytest.fixture
def wrapper():
    env = {"SUPABASE_URL": "http://127.0.0.1:9", "SUPABASE_ANON_KEY": "offline-test-placeholder"}
    with patch.dict(os.environ, env):
        os.environ.pop("SUPABASE_SERVICE_KEY", None)
        real = SupabaseClient()
    assert real.admin_client is None
    return real


def test_wrapper_rpc_delegates_to_supabase_py(wrapper):
    wrapper.client = _fake_supabase_py([{"ok": True}])

    result = wrapper.rpc("some_function", {"p": 1}).execute()

    wrapper.client.rpc.assert_called_once_with("some_function", {"p": 1})
    assert result.data == [{"ok": True}]


def test_wrapper_rpc_prefers_admin_client_like_table(wrapper):
    wrapper.client = _fake_supabase_py([])
    wrapper.admin_client = _fake_supabase_py([{"admin": True}])

    result = wrapper.rpc("some_function").execute()

    wrapper.admin_client.rpc.assert_called_once_with("some_function", {})
    wrapper.client.rpc.assert_not_called()
    assert result.data == [{"admin": True}]


async def test_subscription_spend_summary_through_real_wrapper(wrapper):
    wrapper.client = _fake_supabase_py(
        [
            {
                "total_monthly_cost": "150.00",
                "total_yearly_cost": "1800.00",
                "active_subscriptions": 5,
                "by_category": {"llm_provider": "150.00"},
            }
        ]
    )

    summary = await SubscriptionService(supabase_client=wrapper).get_spend_summary("user-1")

    wrapper.client.rpc.assert_called_once_with("get_monthly_spend_summary", {"p_user_id": "user-1"})
    assert summary.total_monthly_cost == Decimal("150.00")


async def test_subscription_upcoming_alerts_through_real_wrapper(wrapper):
    wrapper.client = _fake_supabase_py([])

    await SubscriptionService(supabase_client=wrapper).get_upcoming_alerts("user-1")

    wrapper.client.rpc.assert_called_once_with(
        "get_upcoming_billing_alerts", {"p_user_id": "user-1"}
    )


async def test_enterprise_department_spend_through_real_wrapper(wrapper):
    wrapper.client = _fake_supabase_py(
        [{"department_name": "Eng", "budget_usd": 100, "total_spend": 25}]
    )

    summary = await EnterpriseService(supabase_client=wrapper).get_department_spend("dept-1")

    wrapper.client.rpc.assert_called_once_with("get_department_spend", {"dept_id": "dept-1"})
    assert summary.department_name == "Eng"


async def test_enterprise_budget_compliance_through_real_wrapper(wrapper):
    wrapper.client = _fake_supabase_py([{"budget_percent": 92.0}])

    alerts = await EnterpriseService(supabase_client=wrapper).check_budget_compliance("dept-1")

    wrapper.client.rpc.assert_called_once_with("get_department_spend", {"dept_id": "dept-1"})
    assert len(alerts) == 1
