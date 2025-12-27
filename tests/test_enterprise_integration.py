"""
Integration Tests for Enterprise Multi-Tenant Features

These tests run against a real Supabase database.
They are skipped if SUPABASE_URL/SUPABASE_SERVICE_KEY are not set.

Test data is cleaned up after each test to maintain isolation.

Run with: pytest tests/test_enterprise_integration.py -v
"""

import os
from dotenv import load_dotenv

# Load .env BEFORE checking for credentials
load_dotenv()

import pytest
import asyncio
from datetime import datetime, timezone
from uuid import uuid4

# Skip entire module if Supabase credentials not available
# Requires both URL and SERVICE_KEY for integration tests (admin access needed)
_supabase_configured = (
    os.environ.get("SUPABASE_URL") and
    os.environ.get("SUPABASE_ANON_KEY") and
    os.environ.get("SUPABASE_SERVICE_KEY")
)


def _check_supabase_connectivity():
    """Check if Supabase is reachable (for CI environments without network access)."""
    if not _supabase_configured:
        return False
    try:
        import httpx
        url = os.environ.get("SUPABASE_URL")
        response = httpx.get(f"{url}/rest/v1/", timeout=5.0)
        return response.status_code in (200, 401)  # 401 = no auth but reachable
    except Exception:
        return False


_supabase_reachable = _check_supabase_connectivity()

pytestmark = pytest.mark.skipif(
    not _supabase_reachable,
    reason="Supabase not reachable (credentials missing or network unavailable)"
)


@pytest.fixture(scope="module")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def supabase_client():
    """Get raw Supabase admin client for direct table operations in tests."""
    from app.database.supabase_client import get_supabase_client
    wrapper = get_supabase_client()
    # Use admin_client which bypasses RLS for test setup/cleanup
    if wrapper.admin_client is None:
        pytest.skip("SUPABASE_SERVICE_KEY required for integration tests")
    return wrapper.admin_client


@pytest.fixture(scope="module")
def enterprise_service():
    """Get real enterprise service for integration tests."""
    from app.services.enterprise_service import EnterpriseService
    return EnterpriseService()


@pytest.fixture
def test_org_id():
    """Generate unique organization ID for test isolation."""
    return f"test-org-{uuid4().hex[:8]}"


@pytest.fixture
def test_employee_id():
    """Generate unique employee ID for test isolation."""
    return f"test-emp-{uuid4().hex[:8]}"


class TestOrganizationIntegration:
    """Integration tests for organization CRUD operations."""

    @pytest.fixture(autouse=True)
    def cleanup(self, supabase_client, test_org_id):
        """Clean up test organization after each test."""
        yield
        # Cleanup: delete test organization and related data
        try:
            supabase_client.table("organizations").delete().eq(
                "id", test_org_id
            ).execute()
        except Exception:
            pass  # Ignore cleanup errors

    @pytest.mark.asyncio
    async def test_create_organization_real_db(self, enterprise_service, test_org_id):
        """Create organization in real Supabase database."""
        org = await enterprise_service.create_organization(
            name=f"Test Corp {test_org_id}",
            domain="testcorp.io",
            plan="starter",
            settings={"blocked_providers": ["deepseek"]}
        )

        assert org is not None
        assert org.name == f"Test Corp {test_org_id}"
        assert org.domain == "testcorp.io"
        assert org.plan == "starter"
        assert "deepseek" in org.settings.get("blocked_providers", [])

    @pytest.mark.asyncio
    async def test_get_organization_real_db(self, enterprise_service, supabase_client, test_org_id):
        """Get organization from real Supabase database."""
        # First create the organization
        supabase_client.table("organizations").insert({
            "id": test_org_id,
            "name": f"Existing Corp {test_org_id}",
            "domain": "existing.io",
            "plan": "enterprise",
            "settings": {"budget_limit_usd": 10000}
        }).execute()

        # Then fetch it via service
        org = await enterprise_service.get_organization(test_org_id)

        assert org is not None
        assert org.id == test_org_id
        assert org.name == f"Existing Corp {test_org_id}"
        assert org.plan == "enterprise"

    @pytest.mark.asyncio
    async def test_update_organization_settings_real_db(self, enterprise_service, supabase_client, test_org_id):
        """Update organization settings in real database."""
        # Create org first
        supabase_client.table("organizations").insert({
            "id": test_org_id,
            "name": f"Update Test Corp {test_org_id}",
            "plan": "growth",
            "settings": {}
        }).execute()

        # Update settings
        updated = await enterprise_service.update_organization_settings(
            test_org_id,
            {"blocked_providers": ["qwen", "baidu"], "require_approval": True}
        )

        assert updated is not None
        assert "qwen" in updated.settings.get("blocked_providers", [])
        assert "baidu" in updated.settings.get("blocked_providers", [])
        assert updated.settings.get("require_approval") is True


class TestEmployeeIntegration:
    """Integration tests for employee management."""

    @pytest.fixture(autouse=True)
    def cleanup(self, supabase_client, test_org_id, test_employee_id):
        """Clean up test data after each test."""
        yield
        # Cleanup in reverse dependency order
        try:
            supabase_client.table("employee_api_keys").delete().eq(
                "employee_id", test_employee_id
            ).execute()
        except Exception:
            pass
        try:
            supabase_client.table("employees").delete().eq(
                "id", test_employee_id
            ).execute()
        except Exception:
            pass
        try:
            supabase_client.table("organizations").delete().eq(
                "id", test_org_id
            ).execute()
        except Exception:
            pass

    @pytest.fixture
    def setup_org(self, supabase_client, test_org_id):
        """Create test organization for employee tests."""
        supabase_client.table("organizations").insert({
            "id": test_org_id,
            "name": f"Employee Test Corp {test_org_id}",
            "plan": "enterprise",
            "settings": {}
        }).execute()
        return test_org_id

    @pytest.mark.asyncio
    async def test_add_employee_real_db(self, enterprise_service, setup_org, test_employee_id):
        """Add employee to real Supabase database."""
        employee = await enterprise_service.add_employee(
            org_id=setup_org,
            email="tim@coperniq.io",
            name="Tim Kipper",
            role="admin"
        )

        assert employee is not None
        assert employee.email == "tim@coperniq.io"
        assert employee.name == "Tim Kipper"
        assert employee.role == "admin"
        assert employee.org_id == setup_org

    @pytest.mark.asyncio
    async def test_link_personal_account_real_db(
        self, enterprise_service, supabase_client, setup_org, test_employee_id
    ):
        """Link personal email with GDPR consent in real database."""
        # Create employee first
        supabase_client.table("employees").insert({
            "id": test_employee_id,
            "org_id": setup_org,
            "email": "work@coperniq.io",
            "name": "Test User",
            "role": "employee",
            "is_active": True
        }).execute()

        # Link personal account
        updated = await enterprise_service.link_personal_account(
            employee_id=test_employee_id,
            personal_email="personal@gmail.com",
            consent=True
        )

        assert updated is not None
        assert updated.personal_email == "personal@gmail.com"
        assert updated.personal_consent is True
        assert updated.personal_linked_at is not None


class TestAPIKeyIntegration:
    """Integration tests for API key management with encryption."""

    @pytest.fixture(autouse=True)
    def cleanup(self, supabase_client, test_org_id, test_employee_id):
        """Clean up test data after each test."""
        yield
        try:
            supabase_client.table("employee_api_keys").delete().eq(
                "employee_id", test_employee_id
            ).execute()
        except Exception:
            pass
        try:
            supabase_client.table("employees").delete().eq(
                "id", test_employee_id
            ).execute()
        except Exception:
            pass
        try:
            supabase_client.table("organizations").delete().eq(
                "id", test_org_id
            ).execute()
        except Exception:
            pass

    @pytest.fixture
    def setup_employee(self, supabase_client, test_org_id, test_employee_id):
        """Create test organization and employee."""
        supabase_client.table("organizations").insert({
            "id": test_org_id,
            "name": f"API Key Test Corp {test_org_id}",
            "plan": "enterprise",
            "settings": {}
        }).execute()

        supabase_client.table("employees").insert({
            "id": test_employee_id,
            "org_id": test_org_id,
            "email": "apitest@coperniq.io",
            "role": "employee",
            "is_active": True
        }).execute()

        return test_employee_id

    @pytest.mark.asyncio
    async def test_add_api_key_encrypted_real_db(self, enterprise_service, setup_employee):
        """Add API key with encryption in real database."""
        api_key = await enterprise_service.add_employee_api_key(
            employee_id=setup_employee,
            provider="anthropic",
            api_key="sk-ant-api03-test-key-1234567890abcdef",
            account_type="work"
        )

        assert api_key is not None
        assert api_key.provider == "anthropic"
        assert api_key.account_type == "work"
        assert api_key.key_last_four == "cdef"  # Last 4 chars of the key
        assert api_key.is_approved is False  # Needs approval by default
        assert api_key.is_active is True

    @pytest.mark.asyncio
    async def test_get_employee_api_keys_real_db(
        self, enterprise_service, supabase_client, setup_employee
    ):
        """Get employee's API keys from real database."""
        # Add keys directly to DB (bypassing service to test retrieval)
        from app.services.encryption_service import get_encryption_service
        encryption = get_encryption_service()

        for provider in ["anthropic", "openai"]:
            supabase_client.table("employee_api_keys").insert({
                "employee_id": setup_employee,
                "provider": provider,
                "account_type": "work",
                "api_key_encrypted": encryption.encrypt(f"sk-test-{provider}-key"),
                "key_last_four": "key1",
                "is_active": True,
                "is_approved": True
            }).execute()

        # Fetch via service
        keys = await enterprise_service.get_employee_api_keys(setup_employee)

        assert len(keys) == 2
        providers = {k.provider for k in keys}
        assert "anthropic" in providers
        assert "openai" in providers

    @pytest.mark.asyncio
    async def test_approve_api_key_real_db(
        self, enterprise_service, supabase_client, setup_employee
    ):
        """Approve API key in real database."""
        from app.services.encryption_service import get_encryption_service
        encryption = get_encryption_service()

        # Create unapproved key
        key_id = f"key-{uuid4().hex[:8]}"
        supabase_client.table("employee_api_keys").insert({
            "id": key_id,
            "employee_id": setup_employee,
            "provider": "gemini",
            "account_type": "work",
            "api_key_encrypted": encryption.encrypt("test-gemini-key"),
            "key_last_four": "key2",
            "is_active": True,
            "is_approved": False
        }).execute()

        # Approve via service
        admin_id = f"admin-{uuid4().hex[:8]}"
        approved = await enterprise_service.approve_api_key(
            key_id=key_id,
            approved_by=admin_id,
            notes="Approved for production use"
        )

        assert approved is not None
        assert approved.is_approved is True
        assert approved.approved_by == admin_id
        assert approved.compliance_notes == "Approved for production use"


class TestComplianceIntegration:
    """Integration tests for compliance alerts."""

    @pytest.fixture(autouse=True)
    def cleanup(self, supabase_client, test_org_id, test_employee_id):
        """Clean up test data after each test."""
        yield
        try:
            supabase_client.table("compliance_alerts").delete().eq(
                "org_id", test_org_id
            ).execute()
        except Exception:
            pass
        try:
            supabase_client.table("employees").delete().eq(
                "id", test_employee_id
            ).execute()
        except Exception:
            pass
        try:
            supabase_client.table("organizations").delete().eq(
                "id", test_org_id
            ).execute()
        except Exception:
            pass

    @pytest.fixture
    def setup_org_employee(self, supabase_client, test_org_id, test_employee_id):
        """Create test organization and employee for compliance tests."""
        supabase_client.table("organizations").insert({
            "id": test_org_id,
            "name": f"Compliance Test Corp {test_org_id}",
            "plan": "enterprise",
            "settings": {"blocked_providers": ["deepseek"]}
        }).execute()

        supabase_client.table("employees").insert({
            "id": test_employee_id,
            "org_id": test_org_id,
            "email": "compliance@coperniq.io",
            "role": "employee",
            "is_active": True
        }).execute()

        return {"org_id": test_org_id, "employee_id": test_employee_id}

    @pytest.mark.asyncio
    async def test_get_compliance_alerts_real_db(
        self, enterprise_service, supabase_client, setup_org_employee
    ):
        """Get compliance alerts from real database."""
        org_id = setup_org_employee["org_id"]
        employee_id = setup_org_employee["employee_id"]

        # Create alerts directly
        supabase_client.table("compliance_alerts").insert([
            {
                "org_id": org_id,
                "employee_id": employee_id,
                "alert_type": "chinese_provider",
                "severity": "critical",
                "provider": "deepseek",
                "title": "Chinese Provider Usage",
                "message": "DeepSeek usage detected",
                "resolved": False
            },
            {
                "org_id": org_id,
                "employee_id": employee_id,
                "alert_type": "budget_warning",
                "severity": "warning",
                "title": "Budget Warning",
                "message": "80% of budget used",
                "resolved": True
            }
        ]).execute()

        # Get unresolved alerts
        alerts = await enterprise_service.get_compliance_alerts(
            org_id, resolved=False
        )

        assert len(alerts) == 1
        assert alerts[0].alert_type == "chinese_provider"
        assert alerts[0].severity == "critical"
        assert alerts[0].resolved is False

    @pytest.mark.asyncio
    async def test_resolve_alert_real_db(
        self, enterprise_service, supabase_client, setup_org_employee
    ):
        """Resolve compliance alert in real database."""
        org_id = setup_org_employee["org_id"]
        employee_id = setup_org_employee["employee_id"]

        # Create alert
        alert_id = f"alert-{uuid4().hex[:8]}"
        supabase_client.table("compliance_alerts").insert({
            "id": alert_id,
            "org_id": org_id,
            "employee_id": employee_id,
            "alert_type": "chinese_provider",
            "severity": "critical",
            "title": "Chinese Provider Usage",
            "message": "DeepSeek usage detected",
            "resolved": False
        }).execute()

        # Resolve via service
        admin_id = f"admin-{uuid4().hex[:8]}"
        resolved = await enterprise_service.resolve_alert(
            alert_id=alert_id,
            resolved_by=admin_id,
            notes="Approved for one-time research use"
        )

        assert resolved is not None
        assert resolved.resolved is True
        assert resolved.resolved_by == admin_id
        assert resolved.resolution_notes == "Approved for one-time research use"


class TestChineseProviderCompliance:
    """Integration tests for Chinese AI provider compliance checks."""

    @pytest.mark.asyncio
    async def test_get_chinese_providers_real_db(self, enterprise_service):
        """Get Chinese AI providers from real database."""
        providers = await enterprise_service.get_chinese_providers()

        # Should return pre-seeded Chinese providers
        provider_ids = {p.id for p in providers}

        # At minimum, check the structure is correct
        for provider in providers:
            assert provider.headquarters_country == "CN"
            assert provider.is_chinese_company is True
            assert provider.risk_level in ["high", "blocked"]

    @pytest.mark.asyncio
    async def test_is_provider_blocked_real_db(
        self, enterprise_service, supabase_client, test_org_id
    ):
        """Check if provider is blocked by organization policy."""
        # Create org with blocked providers
        supabase_client.table("organizations").insert({
            "id": test_org_id,
            "name": f"Block Test Corp {test_org_id}",
            "plan": "enterprise",
            "settings": {"blocked_providers": ["deepseek", "qwen"]}
        }).execute()

        try:
            # Check blocked provider
            is_blocked = await enterprise_service.is_provider_blocked(
                test_org_id, "deepseek"
            )
            assert is_blocked is True

            # Check allowed provider
            is_blocked = await enterprise_service.is_provider_blocked(
                test_org_id, "anthropic"
            )
            assert is_blocked is False
        finally:
            # Cleanup
            supabase_client.table("organizations").delete().eq(
                "id", test_org_id
            ).execute()


class TestEndToEndWorkflow:
    """End-to-end integration tests for complete enterprise workflows."""

    @pytest.fixture(autouse=True)
    def cleanup(self, supabase_client):
        """Clean up all test data after each test."""
        self._test_ids = {
            "org_id": f"e2e-org-{uuid4().hex[:8]}",
            "employee_id": f"e2e-emp-{uuid4().hex[:8]}"
        }
        yield
        # Cleanup in reverse dependency order
        try:
            supabase_client.table("compliance_alerts").delete().eq(
                "org_id", self._test_ids["org_id"]
            ).execute()
        except Exception:
            pass
        try:
            supabase_client.table("employee_api_keys").delete().eq(
                "employee_id", self._test_ids["employee_id"]
            ).execute()
        except Exception:
            pass
        try:
            supabase_client.table("employees").delete().eq(
                "id", self._test_ids["employee_id"]
            ).execute()
        except Exception:
            pass
        try:
            supabase_client.table("organizations").delete().eq(
                "id", self._test_ids["org_id"]
            ).execute()
        except Exception:
            pass

    @pytest.mark.asyncio
    async def test_complete_onboarding_workflow(self, enterprise_service):
        """Test complete enterprise onboarding workflow."""
        org_id = self._test_ids["org_id"]

        # Step 1: Create organization
        org = await enterprise_service.create_organization(
            name="Coperniq Inc",
            domain="coperniq.io",
            plan="enterprise",
            settings={
                "blocked_providers": ["deepseek", "qwen", "baidu"],
                "require_approval": True,
                "budget_limit_usd": 50000
            }
        )
        assert org is not None
        self._test_ids["org_id"] = org.id  # Update with actual ID

        # Step 2: Add admin employee
        admin = await enterprise_service.add_employee(
            org_id=org.id,
            email="tim@coperniq.io",
            name="Tim Kipper",
            role="admin"
        )
        assert admin is not None
        assert admin.role == "admin"
        self._test_ids["employee_id"] = admin.id

        # Step 3: Link personal account
        updated_admin = await enterprise_service.link_personal_account(
            employee_id=admin.id,
            personal_email="tkipper@gmail.com",
            consent=True
        )
        assert updated_admin.personal_email == "tkipper@gmail.com"
        assert updated_admin.personal_consent is True

        # Step 4: Add API keys (work + personal)
        work_key = await enterprise_service.add_employee_api_key(
            employee_id=admin.id,
            provider="anthropic",
            api_key="sk-ant-work-key-1234567890abcdef",
            account_type="work"
        )
        assert work_key.account_type == "work"
        assert work_key.is_approved is False  # Needs approval

        personal_key = await enterprise_service.add_employee_api_key(
            employee_id=admin.id,
            provider="openai",
            api_key="sk-personal-key-0987654321fedcba",
            account_type="personal"
        )
        assert personal_key.account_type == "personal"

        # Step 5: Verify API keys list
        keys = await enterprise_service.get_employee_api_keys(admin.id)
        assert len(keys) == 2
        providers = {k.provider for k in keys}
        assert "anthropic" in providers
        assert "openai" in providers

        # Step 6: Check Chinese provider blocking
        is_blocked = await enterprise_service.is_provider_blocked(org.id, "deepseek")
        assert is_blocked is True

        is_blocked = await enterprise_service.is_provider_blocked(org.id, "anthropic")
        assert is_blocked is False
