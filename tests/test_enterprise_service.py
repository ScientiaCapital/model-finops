"""
TDD Tests for Enterprise Service (RED Phase)

Test business logic for organizations, employees, API keys, and compliance.
Written BEFORE implementation (TDD approach).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_supabase():
    """Mock Supabase client for testing."""
    mock = MagicMock()
    mock.table = MagicMock(return_value=mock)
    mock.select = MagicMock(return_value=mock)
    mock.insert = MagicMock(return_value=mock)
    mock.update = MagicMock(return_value=mock)
    mock.delete = MagicMock(return_value=mock)
    mock.eq = MagicMock(return_value=mock)
    mock.execute = MagicMock(return_value=MagicMock(data=[]))
    return mock


@pytest.fixture
def mock_encryption():
    """Mock encryption service."""
    mock = MagicMock()
    mock.encrypt = MagicMock(return_value="encrypted_key_xxx")
    mock.decrypt = MagicMock(return_value="sk-ant-api03-original")
    mock.get_key_last_four = MagicMock(return_value="ABCD")
    return mock


@pytest.fixture
def enterprise_service(mock_supabase, mock_encryption):
    """Create EnterpriseService with mocked dependencies."""
    from app.services.enterprise_service import EnterpriseService
    return EnterpriseService(
        supabase_client=mock_supabase,
        encryption_service=mock_encryption
    )


# =============================================================================
# Organization Tests
# =============================================================================

class TestOrganizationService:
    """Test organization CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_organization(self, enterprise_service, mock_supabase):
        """Should create an organization with default settings."""
        mock_supabase.execute.return_value.data = [{
            "id": "org-123",
            "name": "Coperniq",
            "domain": "coperniq.io",
            "plan": "starter",
            "settings": {},
            "created_at": datetime.now().isoformat()
        }]

        org = await enterprise_service.create_organization(
            name="Coperniq",
            domain="coperniq.io"
        )

        assert org.id == "org-123"
        assert org.name == "Coperniq"
        assert org.domain == "coperniq.io"

    @pytest.mark.asyncio
    async def test_create_organization_with_settings(self, enterprise_service, mock_supabase):
        """Should create org with custom AI policy settings."""
        settings = {
            "blocked_providers": ["deepseek"],
            "max_monthly_budget_usd": 10000
        }
        mock_supabase.execute.return_value.data = [{
            "id": "org-123",
            "name": "Coperniq",
            "domain": "coperniq.io",
            "plan": "enterprise",
            "settings": settings,
            "created_at": datetime.now().isoformat()
        }]

        org = await enterprise_service.create_organization(
            name="Coperniq",
            domain="coperniq.io",
            plan="enterprise",
            settings=settings
        )

        assert org.settings["blocked_providers"] == ["deepseek"]

    @pytest.mark.asyncio
    async def test_get_organization(self, enterprise_service, mock_supabase):
        """Should retrieve organization by ID."""
        mock_supabase.execute.return_value.data = [{
            "id": "org-123",
            "name": "Coperniq",
            "domain": "coperniq.io",
            "plan": "starter",
            "settings": {},
            "created_at": datetime.now().isoformat()
        }]

        org = await enterprise_service.get_organization("org-123")

        assert org.id == "org-123"

    @pytest.mark.asyncio
    async def test_get_organization_not_found(self, enterprise_service, mock_supabase):
        """Should return None for non-existent org."""
        mock_supabase.execute.return_value.data = []

        org = await enterprise_service.get_organization("nonexistent")

        assert org is None


# =============================================================================
# Employee Tests
# =============================================================================

class TestEmployeeService:
    """Test employee CRUD operations."""

    @pytest.mark.asyncio
    async def test_add_employee(self, enterprise_service, mock_supabase):
        """Should add employee to organization."""
        mock_supabase.execute.return_value.data = [{
            "id": "emp-123",
            "org_id": "org-123",
            "email": "tim@coperniq.io",
            "name": "Tim Kipper",
            "role": "employee",
            "is_active": True,
            "created_at": datetime.now().isoformat()
        }]

        emp = await enterprise_service.add_employee(
            org_id="org-123",
            email="tim@coperniq.io",
            name="Tim Kipper"
        )

        assert emp.email == "tim@coperniq.io"
        assert emp.role == "employee"

    @pytest.mark.asyncio
    async def test_add_employee_as_manager(self, enterprise_service, mock_supabase):
        """Should add employee with manager role."""
        mock_supabase.execute.return_value.data = [{
            "id": "emp-123",
            "org_id": "org-123",
            "email": "tim@coperniq.io",
            "role": "manager",
            "is_active": True,
            "created_at": datetime.now().isoformat()
        }]

        emp = await enterprise_service.add_employee(
            org_id="org-123",
            email="tim@coperniq.io",
            role="manager"
        )

        assert emp.role == "manager"

    @pytest.mark.asyncio
    async def test_link_personal_account(self, enterprise_service, mock_supabase):
        """Should link personal email with GDPR consent."""
        mock_supabase.execute.return_value.data = [{
            "id": "emp-123",
            "org_id": "org-123",
            "email": "tim@coperniq.io",
            "role": "employee",
            "personal_email": "tkipper@gmail.com",
            "personal_consent": True,
            "personal_linked_at": datetime.now().isoformat(),
            "is_active": True,
            "created_at": datetime.now().isoformat()
        }]

        emp = await enterprise_service.link_personal_account(
            employee_id="emp-123",
            personal_email="tkipper@gmail.com",
            consent=True
        )

        assert emp.personal_email == "tkipper@gmail.com"
        assert emp.personal_consent is True
        assert emp.personal_linked_at is not None

    @pytest.mark.asyncio
    async def test_link_personal_requires_consent(self, enterprise_service):
        """Should reject personal linking without consent."""
        with pytest.raises(ValueError) as exc_info:
            await enterprise_service.link_personal_account(
                employee_id="emp-123",
                personal_email="tkipper@gmail.com",
                consent=False
            )
        assert "consent" in str(exc_info.value).lower()


# =============================================================================
# API Key Tests
# =============================================================================

class TestAPIKeyService:
    """Test API key management with encryption."""

    @pytest.mark.asyncio
    async def test_add_api_key_encrypted(self, enterprise_service, mock_supabase, mock_encryption):
        """Should encrypt API key before storage."""
        mock_supabase.execute.return_value.data = [{
            "id": "key-123",
            "employee_id": "emp-123",
            "provider": "anthropic",
            "account_type": "work",
            "api_key_encrypted": "encrypted_key_xxx",
            "key_last_four": "ABCD",
            "is_approved": False,
            "is_active": True,
            "created_at": datetime.now().isoformat()
        }]

        key = await enterprise_service.add_employee_api_key(
            employee_id="emp-123",
            provider="anthropic",
            api_key="sk-ant-api03-WpxBupWjWFUU-ABCD",
            account_type="work"
        )

        # Verify encryption was called
        mock_encryption.encrypt.assert_called_once()
        mock_encryption.get_key_last_four.assert_called_once()

        # Response should not expose encrypted key
        assert key.key_last_four == "ABCD"

    @pytest.mark.asyncio
    async def test_add_personal_api_key(self, enterprise_service, mock_supabase):
        """Should add API key for personal account."""
        mock_supabase.execute.return_value.data = [{
            "id": "key-123",
            "employee_id": "emp-123",
            "provider": "anthropic",
            "account_type": "personal",
            "api_key_encrypted": "encrypted",
            "key_last_four": "1234",
            "is_approved": False,
            "is_active": True,
            "created_at": datetime.now().isoformat()
        }]

        key = await enterprise_service.add_employee_api_key(
            employee_id="emp-123",
            provider="anthropic",
            api_key="sk-ant-personal-1234",
            account_type="personal"
        )

        assert key.account_type == "personal"

    @pytest.mark.asyncio
    async def test_approve_api_key(self, enterprise_service, mock_supabase):
        """HR admin should be able to approve API key."""
        mock_supabase.execute.return_value.data = [{
            "id": "key-123",
            "employee_id": "emp-123",
            "provider": "anthropic",
            "account_type": "work",
            "key_last_four": "ABCD",
            "is_approved": True,
            "approved_by": "hr-admin-123",
            "approved_at": datetime.now().isoformat(),
            "is_active": True,
            "created_at": datetime.now().isoformat()
        }]

        key = await enterprise_service.approve_api_key(
            key_id="key-123",
            approved_by="hr-admin-123",
            notes="Approved for production use"
        )

        assert key.is_approved is True
        assert key.approved_by == "hr-admin-123"

    @pytest.mark.asyncio
    async def test_revoke_api_key(self, enterprise_service, mock_supabase):
        """Should revoke API key and record reason."""
        mock_supabase.execute.return_value.data = [{
            "id": "key-123",
            "employee_id": "emp-123",
            "provider": "anthropic",
            "account_type": "work",
            "key_last_four": "ABCD",
            "is_active": False,
            "revoked_at": datetime.now().isoformat(),
            "revoked_by": "hr-admin-123",
            "revoke_reason": "Employee offboarding",
            "created_at": datetime.now().isoformat()
        }]

        key = await enterprise_service.revoke_api_key(
            key_id="key-123",
            revoked_by="hr-admin-123",
            reason="Employee offboarding"
        )

        assert key.is_active is False


# =============================================================================
# Usage Logging Tests
# =============================================================================

class TestUsageLogging:
    """Test AI usage logging and compliance."""

    @pytest.mark.asyncio
    async def test_log_usage(self, enterprise_service, mock_supabase):
        """Should log AI usage with cost tracking."""
        mock_supabase.execute.return_value.data = [{
            "id": "usage-123",
            "employee_id": "emp-123",
            "provider": "anthropic",
            "model": "claude-3-opus",
            "input_tokens": 1000,
            "output_tokens": 500,
            "cost_usd": 0.05,
            "account_type": "work",
            "flagged_for_review": False,
            "created_at": datetime.now().isoformat()
        }]

        usage = await enterprise_service.log_usage(
            employee_id="emp-123",
            provider="anthropic",
            model="claude-3-opus",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=0.05,
            account_type="work"
        )

        assert usage.cost_usd == 0.05
        assert usage.total_tokens == 1500

    @pytest.mark.asyncio
    async def test_chinese_provider_triggers_alert(self, enterprise_service, mock_supabase):
        """Usage of Chinese provider should create compliance alert."""
        # Mock sequence of calls: provider lookup, employee lookup, alert insert, usage insert
        mock_supabase.execute.side_effect = [
            # Provider info lookup
            MagicMock(data=[{
                "id": "deepseek",
                "display_name": "DeepSeek",
                "headquarters_country": "CN",
                "risk_level": "high",
                "data_residency": ["cn"]
            }]),
            # Employee lookup
            MagicMock(data=[{
                "id": "emp-123",
                "org_id": "org-123",
                "email": "tim@coperniq.io",
                "name": "Tim",
                "role": "employee",
                "is_active": True,
                "created_at": datetime.now().isoformat()
            }]),
            # Alert insert
            MagicMock(data=[{
                "id": "alert-1",
                "org_id": "org-123",
                "alert_type": "chinese_provider",
                "severity": "critical",
                "title": "Chinese AI Provider Usage Detected",
                "message": "Test message",
                "resolved": False,
                "created_at": datetime.now().isoformat()
            }]),
            # Usage log insert
            MagicMock(data=[{
                "id": "usage-123",
                "employee_id": "emp-123",
                "provider": "deepseek",
                "cost_usd": 0.01,
                "flagged_for_review": False,
                "created_at": datetime.now().isoformat()
            }])
        ]

        # Should trigger alert creation
        alerts = await enterprise_service.log_usage_with_compliance(
            employee_id="emp-123",
            org_id="org-123",
            provider="deepseek",
            model="deepseek-chat",
            cost_usd=0.01
        )

        assert len(alerts) >= 1
        assert any(a.alert_type == "chinese_provider" for a in alerts)

    @pytest.mark.asyncio
    async def test_budget_threshold_alert(self, enterprise_service, mock_supabase):
        """Should alert when department exceeds budget threshold."""
        # Mock RPC call for department spend
        mock_supabase.rpc = MagicMock(return_value=mock_supabase)
        mock_supabase.execute.return_value = MagicMock(data=[{
            "total_spend": 8500,
            "budget_usd": 10000,
            "budget_percent": 85.0,
            "department_name": "Engineering"
        }])

        alerts = await enterprise_service.check_budget_compliance(
            dept_id="dept-123",
            threshold_percent=80
        )

        assert len(alerts) >= 1
        assert alerts[0].alert_type == "budget_warning"
        assert alerts[0].severity == "warning"


# =============================================================================
# Compliance Alerts Tests
# =============================================================================

class TestComplianceAlerts:
    """Test compliance alert management."""

    @pytest.mark.asyncio
    async def test_get_compliance_alerts(self, enterprise_service, mock_supabase):
        """Should retrieve compliance alerts for organization."""
        mock_supabase.order = MagicMock(return_value=mock_supabase)
        mock_supabase.limit = MagicMock(return_value=mock_supabase)
        mock_supabase.execute.return_value = MagicMock(data=[
            {
                "id": "alert-1",
                "org_id": "org-123",
                "alert_type": "chinese_provider",
                "severity": "critical",
                "title": "Chinese AI Usage",
                "message": "Employee used DeepSeek",
                "details": {},
                "resolved": False,
                "created_at": datetime.now().isoformat()
            }
        ])

        alerts = await enterprise_service.get_compliance_alerts(
            org_id="org-123",
            resolved=False
        )

        assert len(alerts) == 1
        assert alerts[0].alert_type == "chinese_provider"

    @pytest.mark.asyncio
    async def test_resolve_alert(self, enterprise_service, mock_supabase):
        """HR admin should resolve compliance alert."""
        mock_supabase.execute.return_value = MagicMock(data=[{
            "id": "alert-1",
            "org_id": "org-123",
            "alert_type": "chinese_provider",
            "severity": "critical",
            "title": "Chinese AI Usage",
            "message": "Employee used DeepSeek",
            "details": {},
            "resolved": True,
            "resolved_by": "hr-admin-123",
            "resolved_at": datetime.now().isoformat(),
            "resolution_notes": "Approved for research use",
            "created_at": datetime.now().isoformat()
        }])

        alert = await enterprise_service.resolve_alert(
            alert_id="alert-1",
            resolved_by="hr-admin-123",
            notes="Approved for research use"
        )

        assert alert.resolved is True
        assert "research" in alert.resolution_notes.lower()


# =============================================================================
# Analytics Tests
# =============================================================================

class TestAnalytics:
    """Test spend and usage analytics."""

    @pytest.mark.asyncio
    async def test_get_department_spend(self, enterprise_service, mock_supabase):
        """Should calculate department spend summary."""
        mock_supabase.rpc = MagicMock(return_value=mock_supabase)
        mock_supabase.execute.return_value = MagicMock(data=[{
            "department_name": "Engineering",
            "total_spend": 8500.00,
            "budget_usd": 10000.00,
            "employee_count": 15,
            "top_provider": "anthropic"
        }])

        summary = await enterprise_service.get_department_spend(
            dept_id="dept-123"
        )

        assert summary.total_spend_usd == 8500.00
        assert summary.budget_percent == 85.0
        assert summary.is_over_threshold(80)

    @pytest.mark.asyncio
    async def test_get_employee_spend_summary(self, enterprise_service, mock_supabase):
        """Should calculate employee work vs personal spend."""
        # First call: usage log query, Second call: employee lookup
        mock_supabase.execute.side_effect = [
            MagicMock(data=[
                {"account_type": "work", "cost_usd": 150.00},
                {"account_type": "personal", "cost_usd": 50.00}
            ]),
            MagicMock(data=[{
                "id": "emp-123",
                "org_id": "org-123",
                "email": "tim@coperniq.io",
                "name": "Tim Kipper",
                "role": "employee",
                "is_active": True,
                "created_at": datetime.now().isoformat()
            }])
        ]

        summary = await enterprise_service.get_employee_spend(
            employee_id="emp-123"
        )

        assert summary.work_spend_usd == 150.00
        assert summary.personal_spend_usd == 50.00
        assert summary.total_spend_usd == 200.00

    @pytest.mark.asyncio
    async def test_get_org_spend_by_department(self, enterprise_service, mock_supabase):
        """Should aggregate spend across departments."""
        # Mock department list, then RPC calls for each
        mock_supabase.rpc = MagicMock(return_value=mock_supabase)
        mock_supabase.execute.side_effect = [
            # Department list query
            MagicMock(data=[
                {"id": "dept-1", "name": "Engineering", "budget_usd": 10000},
                {"id": "dept-2", "name": "Sales", "budget_usd": 5000},
                {"id": "dept-3", "name": "Marketing", "budget_usd": 3000}
            ]),
            # RPC for dept-1
            MagicMock(data=[{"total_spend": 5000, "budget_usd": 10000, "employee_count": 10}]),
            # RPC for dept-2
            MagicMock(data=[{"total_spend": 3000, "budget_usd": 5000, "employee_count": 5}]),
            # RPC for dept-3
            MagicMock(data=[{"total_spend": 2000, "budget_usd": 3000, "employee_count": 3}])
        ]

        summaries = await enterprise_service.get_org_spend_by_department(
            org_id="org-123"
        )

        assert len(summaries) == 3
        total = sum(s.total_spend_usd for s in summaries)
        assert total == 10000


# =============================================================================
# Provider Compliance Tests
# =============================================================================

class TestProviderCompliance:
    """Test AI provider compliance checking."""

    @pytest.mark.asyncio
    async def test_is_provider_blocked(self, enterprise_service, mock_supabase):
        """Should check if provider is blocked by org policy."""
        # Mock org settings
        mock_supabase.execute.return_value = MagicMock(data=[{
            "id": "org-123",
            "name": "Coperniq",
            "domain": "coperniq.io",
            "plan": "enterprise",
            "settings": {
                "blocked_providers": ["deepseek", "qwen", "baidu"]
            },
            "created_at": datetime.now().isoformat()
        }])

        is_blocked = await enterprise_service.is_provider_blocked(
            org_id="org-123",
            provider="deepseek"
        )

        assert is_blocked is True

    @pytest.mark.asyncio
    async def test_get_chinese_providers(self, enterprise_service, mock_supabase):
        """Should identify Chinese providers."""
        mock_supabase.execute.return_value.data = [
            {"id": "deepseek", "headquarters_country": "CN", "risk_level": "high"},
            {"id": "qwen", "headquarters_country": "CN", "risk_level": "high"},
            {"id": "baidu", "headquarters_country": "CN", "risk_level": "high"}
        ]

        providers = await enterprise_service.get_chinese_providers()

        assert len(providers) == 3
        assert all(p.is_chinese_company for p in providers)
