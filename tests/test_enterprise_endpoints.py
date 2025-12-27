"""
TDD Tests for Enterprise API Endpoints (GREEN Phase)

Tests for multi-tenant enterprise features:
- Organization management
- Employee API key management (work/personal)
- Personal account linking with GDPR consent
- Compliance alerts for Chinese AI providers
- Spend analytics by department

Uses actual Pydantic models for response validation compatibility.
"""

import pytest
import os
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
from datetime import datetime, timezone

from app.main import app
from app.services.enterprise_service import get_enterprise_service
from app.models.enterprise import (
    OrganizationResponse,
    EmployeeResponse,
    EmployeeAPIKeyResponse,
    EmployeeSpendSummary,
    DepartmentSpendSummary,
    ComplianceAlertResponse,
    AIProviderInfo,
)


# =============================================================================
# Fixtures at module level
# =============================================================================

@pytest.fixture
def mock_enterprise_service():
    """Mock enterprise service for endpoint tests."""
    service = MagicMock()
    # Make async methods return coroutines
    service.create_organization = AsyncMock()
    service.get_organization = AsyncMock()
    service.update_organization_settings = AsyncMock()
    service.add_employee = AsyncMock()
    service.get_employee = AsyncMock()
    service.get_employee_by_auth_user = AsyncMock()
    service.link_personal_account = AsyncMock()
    service.add_employee_api_key = AsyncMock()
    service.get_employee_api_keys = AsyncMock()
    service.approve_api_key = AsyncMock()
    service.revoke_api_key = AsyncMock()
    service.get_employee_spend = AsyncMock()
    service.get_department_spend = AsyncMock()
    service.get_org_spend_by_department = AsyncMock()
    service.get_compliance_alerts = AsyncMock()
    service.resolve_alert = AsyncMock()
    service.get_chinese_providers = AsyncMock()
    service.is_provider_blocked = AsyncMock()
    return service


@pytest.fixture
def enterprise_client(mock_enterprise_service, test_jwt_secret):
    """Test client with mocked enterprise service."""
    # Override the dependency
    app.dependency_overrides[get_enterprise_service] = lambda: mock_enterprise_service

    # Mock the JWT secret
    with patch.dict(os.environ, {"SUPABASE_JWT_SECRET": test_jwt_secret}):
        yield TestClient(app)

    # Clean up
    app.dependency_overrides.clear()


class TestEnterpriseEndpointsAuth:
    """Test authentication requirements for enterprise endpoints."""

    def test_create_org_requires_auth(self, client):
        """Creating organization requires authentication."""
        response = client.post("/api/enterprise/organizations", json={
            "name": "Test Corp",
            "domain": "testcorp.io",
            "plan": "starter"
        })

        assert response.status_code == 401

    def test_add_api_key_requires_auth(self, client):
        """Adding API key requires authentication."""
        response = client.post("/api/enterprise/employees/me/api-keys", json={
            "provider": "anthropic",
            "account_type": "work",
            "api_key": "sk-ant-xxx"
        })

        assert response.status_code == 401

    def test_get_my_usage_requires_auth(self, client):
        """Getting usage dashboard requires authentication."""
        response = client.get("/api/enterprise/employees/me/usage")

        assert response.status_code == 401

    def test_link_personal_requires_auth(self, client):
        """Linking personal account requires authentication."""
        response = client.post("/api/enterprise/employees/me/link-personal", json={
            "personal_email": "personal@gmail.com",
            "consent_given": True
        })

        assert response.status_code == 401

    def test_get_team_usage_requires_auth(self, client):
        """Getting team usage requires authentication."""
        response = client.get("/api/enterprise/team/usage")

        assert response.status_code == 401

    def test_get_compliance_alerts_requires_auth(self, client):
        """Getting compliance alerts requires authentication."""
        response = client.get("/api/enterprise/compliance/alerts")

        assert response.status_code == 401


class TestOrganizationEndpoints:
    """Test organization management endpoints."""

    def test_create_organization_success(self, enterprise_client, auth_headers, mock_enterprise_service):
        """Create organization with valid data."""
        mock_enterprise_service.create_organization.return_value = OrganizationResponse(
            id="org-123",
            name="Test Corp",
            domain="testcorp.io",
            plan="starter",
            settings={},
            created_at=datetime.now(timezone.utc),
            updated_at=None
        )

        response = enterprise_client.post(
            "/api/enterprise/organizations",
            json={
                "name": "Test Corp",
                "domain": "testcorp.io",
                "plan": "starter"
            },
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "org-123"
        assert data["name"] == "Test Corp"
        assert data["plan"] == "starter"

    def test_create_organization_invalid_plan(self, enterprise_client, auth_headers):
        """Reject organization with invalid plan."""
        response = enterprise_client.post(
            "/api/enterprise/organizations",
            json={
                "name": "Test Corp",
                "plan": "super-mega-plan"  # Invalid
            },
            headers=auth_headers
        )

        assert response.status_code == 422

    def test_get_organization_success(self, enterprise_client, auth_headers, mock_enterprise_service):
        """Get organization by ID."""
        mock_enterprise_service.get_organization.return_value = OrganizationResponse(
            id="org-123",
            name="Test Corp",
            domain="testcorp.io",
            plan="enterprise",
            settings={"blocked_providers": ["deepseek", "qwen"]},
            created_at=datetime.now(timezone.utc),
            updated_at=None
        )

        response = enterprise_client.get(
            "/api/enterprise/organizations/org-123",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "org-123"
        assert "deepseek" in data["settings"]["blocked_providers"]

    def test_get_organization_not_found(self, enterprise_client, auth_headers, mock_enterprise_service):
        """Return 404 for non-existent organization."""
        mock_enterprise_service.get_organization.return_value = None

        response = enterprise_client.get(
            "/api/enterprise/organizations/nonexistent",
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_update_organization_settings(self, enterprise_client, auth_headers, mock_enterprise_service):
        """Update organization AI policy settings."""
        mock_enterprise_service.update_organization_settings.return_value = OrganizationResponse(
            id="org-123",
            name="Test Corp",
            domain="testcorp.io",
            plan="enterprise",
            settings={"blocked_providers": ["deepseek", "qwen", "baidu"]},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

        response = enterprise_client.patch(
            "/api/enterprise/organizations/org-123",
            json={
                "settings": {"blocked_providers": ["deepseek", "qwen", "baidu"]}
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "baidu" in response.json()["settings"]["blocked_providers"]


class TestEmployeeAPIKeyEndpoints:
    """Test employee API key management endpoints."""

    def test_add_api_key_work_account(self, enterprise_client, auth_headers, mock_enterprise_service):
        """Add work API key for authenticated employee."""
        mock_enterprise_service.get_employee_by_auth_user.return_value = MagicMock(id="emp-123")
        mock_enterprise_service.add_employee_api_key.return_value = EmployeeAPIKeyResponse(
            id="key-456",
            employee_id="emp-123",
            provider="anthropic",
            account_type="work",
            key_last_four="xxx1",
            is_approved=False,
            approved_by=None,
            approved_at=None,
            data_residency=None,
            compliance_notes=None,
            last_used_at=None,
            total_requests=0,
            total_spend_usd=0.0,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=None
        )

        response = enterprise_client.post(
            "/api/enterprise/employees/me/api-keys",
            json={
                "provider": "anthropic",
                "account_type": "work",
                "api_key": "sk-ant-api03-xxx1"
            },
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["provider"] == "anthropic"
        assert data["key_last_four"] == "xxx1"
        assert data["is_approved"] is False
        # Full API key should NOT be in response
        assert "api_key" not in data
        assert "api_key_encrypted" not in data

    def test_add_api_key_personal_account(self, enterprise_client, auth_headers, mock_enterprise_service):
        """Add personal API key."""
        mock_enterprise_service.get_employee_by_auth_user.return_value = MagicMock(id="emp-123")
        mock_enterprise_service.add_employee_api_key.return_value = EmployeeAPIKeyResponse(
            id="key-789",
            employee_id="emp-123",
            provider="openai",
            account_type="personal",
            key_last_four="sk-2",
            is_approved=False,
            approved_by=None,
            approved_at=None,
            data_residency=None,
            compliance_notes=None,
            last_used_at=None,
            total_requests=0,
            total_spend_usd=0.0,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=None
        )

        response = enterprise_client.post(
            "/api/enterprise/employees/me/api-keys",
            json={
                "provider": "openai",
                "account_type": "personal",
                "api_key": "sk-openai-xxx-sk-2"
            },
            headers=auth_headers
        )

        assert response.status_code == 201
        assert response.json()["account_type"] == "personal"

    def test_add_api_key_invalid_account_type(self, enterprise_client, auth_headers):
        """Reject invalid account type."""
        response = enterprise_client.post(
            "/api/enterprise/employees/me/api-keys",
            json={
                "provider": "anthropic",
                "account_type": "invalid",
                "api_key": "sk-ant-xxx"
            },
            headers=auth_headers
        )

        assert response.status_code == 422

    def test_get_my_api_keys(self, enterprise_client, auth_headers, mock_enterprise_service):
        """Get all API keys for authenticated employee."""
        mock_enterprise_service.get_employee_by_auth_user.return_value = MagicMock(id="emp-123")
        mock_enterprise_service.get_employee_api_keys.return_value = [
            EmployeeAPIKeyResponse(
                id="key-1",
                employee_id="emp-123",
                provider="anthropic",
                account_type="work",
                key_last_four="xxx1",
                is_approved=True,
                approved_by="admin-1",
                approved_at=datetime.now(timezone.utc),
                data_residency=None,
                compliance_notes=None,
                last_used_at=datetime.now(timezone.utc),
                total_requests=150,
                total_spend_usd=12.50,
                is_active=True,
                created_at=datetime.now(timezone.utc),
                updated_at=None
            ),
            EmployeeAPIKeyResponse(
                id="key-2",
                employee_id="emp-123",
                provider="openai",
                account_type="personal",
                key_last_four="sk-2",
                is_approved=False,
                approved_by=None,
                approved_at=None,
                data_residency=None,
                compliance_notes=None,
                last_used_at=None,
                total_requests=0,
                total_spend_usd=0.0,
                is_active=True,
                created_at=datetime.now(timezone.utc),
                updated_at=None
            )
        ]

        response = enterprise_client.get(
            "/api/enterprise/employees/me/api-keys",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["keys"]) == 2
        assert data["keys"][0]["provider"] == "anthropic"
        assert data["keys"][1]["provider"] == "openai"


class TestPersonalAccountLinking:
    """Test personal account linking with GDPR consent."""

    def test_link_personal_account_success(self, enterprise_client, auth_headers, mock_enterprise_service):
        """Link personal email with consent."""
        mock_enterprise_service.get_employee_by_auth_user.return_value = MagicMock(id="emp-123")
        mock_enterprise_service.link_personal_account.return_value = EmployeeResponse(
            id="emp-123",
            org_id="org-1",
            dept_id=None,
            email="tim@coperniq.io",
            name="Tim",
            role="employee",
            personal_email="tkipper@gmail.com",
            personal_linked_at=datetime.now(timezone.utc),
            personal_consent=True,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=None
        )

        response = enterprise_client.post(
            "/api/enterprise/employees/me/link-personal",
            json={
                "personal_email": "tkipper@gmail.com",
                "consent_given": True
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["personal_email"] == "tkipper@gmail.com"
        assert data["personal_consent"] is True

    def test_link_personal_account_no_consent(self, enterprise_client, auth_headers):
        """Reject linking without GDPR consent."""
        response = enterprise_client.post(
            "/api/enterprise/employees/me/link-personal",
            json={
                "personal_email": "personal@gmail.com",
                "consent_given": False  # Must be True
            },
            headers=auth_headers
        )

        # Pydantic validation should reject consent_given=False
        assert response.status_code == 422


class TestUsageEndpoints:
    """Test usage and analytics endpoints."""

    def test_get_my_usage(self, enterprise_client, auth_headers, mock_enterprise_service):
        """Get authenticated employee's usage summary."""
        mock_enterprise_service.get_employee_by_auth_user.return_value = MagicMock(id="emp-123")
        mock_enterprise_service.get_employee_spend.return_value = EmployeeSpendSummary(
            employee_name="Tim",
            email="tim@coperniq.io",
            work_spend_usd=45.50,
            personal_spend_usd=12.30
        )

        response = enterprise_client.get(
            "/api/enterprise/employees/me/usage",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["work_spend_usd"] == 45.50
        assert data["personal_spend_usd"] == 12.30
        assert data["total_spend_usd"] == 57.80

    def test_get_team_usage_as_manager(self, enterprise_client, auth_headers, mock_enterprise_service):
        """Managers can see department usage."""
        mock_enterprise_service.get_employee_by_auth_user.return_value = MagicMock(
            id="emp-123",
            role="manager",
            dept_id="dept-456"
        )
        mock_enterprise_service.get_department_spend.return_value = DepartmentSpendSummary(
            department_name="Engineering",
            total_spend_usd=1500.00,
            budget_usd=5000.00,
            budget_percent=30.0,
            employee_count=15,
            top_provider="anthropic"
        )

        response = enterprise_client.get(
            "/api/enterprise/team/usage",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["department_name"] == "Engineering"
        assert data["total_spend_usd"] == 1500.00
        assert data["budget_percent"] == 30.0

    def test_get_team_usage_as_employee_forbidden(self, enterprise_client, auth_headers, mock_enterprise_service):
        """Regular employees cannot see team usage."""
        mock_enterprise_service.get_employee_by_auth_user.return_value = MagicMock(
            id="emp-123",
            role="employee",  # Not manager
            dept_id="dept-456"
        )

        response = enterprise_client.get(
            "/api/enterprise/team/usage",
            headers=auth_headers
        )

        assert response.status_code == 403

    def test_get_org_spend_by_department(self, enterprise_client, auth_headers, mock_enterprise_service):
        """HR admin can see spend by department."""
        mock_enterprise_service.get_employee_by_auth_user.return_value = MagicMock(
            id="emp-123",
            org_id="org-1",
            role="hr_admin"
        )
        mock_enterprise_service.get_org_spend_by_department.return_value = [
            DepartmentSpendSummary(
                department_name="Engineering",
                total_spend_usd=1500.00,
                budget_usd=5000.00,
                budget_percent=30.0,
                employee_count=15,
                top_provider="anthropic"
            ),
            DepartmentSpendSummary(
                department_name="Marketing",
                total_spend_usd=800.00,
                budget_usd=2000.00,
                budget_percent=40.0,
                employee_count=8,
                top_provider="openai"
            )
        ]

        response = enterprise_client.get(
            "/api/enterprise/org/spend-by-department",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["departments"]) == 2
        assert data["departments"][0]["department_name"] == "Engineering"


class TestComplianceAlerts:
    """Test compliance alert endpoints."""

    def test_get_compliance_alerts(self, enterprise_client, auth_headers, mock_enterprise_service):
        """HR admin can view compliance alerts."""
        mock_enterprise_service.get_employee_by_auth_user.return_value = MagicMock(
            id="emp-123",
            org_id="org-1",
            role="hr_admin"
        )
        mock_enterprise_service.get_compliance_alerts.return_value = [
            ComplianceAlertResponse(
                id="alert-1",
                org_id="org-1",
                employee_id="emp-456",
                dept_id=None,
                alert_type="chinese_provider",
                severity="critical",
                provider="deepseek",
                model="deepseek-chat",
                title="Chinese AI Provider Usage Detected",
                message="Employee John used DeepSeek. Data may be stored in China.",
                details={"cost_usd": 0.50},
                resolved=False,
                resolved_by=None,
                resolved_at=None,
                resolution_notes=None,
                created_at=datetime.now(timezone.utc)
            )
        ]

        response = enterprise_client.get(
            "/api/enterprise/compliance/alerts",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["alerts"]) == 1
        assert data["alerts"][0]["alert_type"] == "chinese_provider"
        assert data["alerts"][0]["severity"] == "critical"
        assert data["alerts"][0]["provider"] == "deepseek"

    def test_get_compliance_alerts_filter_unresolved(self, enterprise_client, auth_headers, mock_enterprise_service):
        """Filter alerts by resolved status."""
        mock_enterprise_service.get_employee_by_auth_user.return_value = MagicMock(
            id="emp-123",
            org_id="org-1",
            role="hr_admin"
        )
        mock_enterprise_service.get_compliance_alerts.return_value = []

        response = enterprise_client.get(
            "/api/enterprise/compliance/alerts?resolved=false",
            headers=auth_headers
        )

        assert response.status_code == 200
        # Verify the service was called with resolved=False filter
        mock_enterprise_service.get_compliance_alerts.assert_called_with(
            "org-1", resolved=False, alert_type=None, limit=100
        )

    def test_get_compliance_alerts_forbidden_for_employee(self, enterprise_client, auth_headers, mock_enterprise_service):
        """Regular employees cannot view compliance alerts."""
        mock_enterprise_service.get_employee_by_auth_user.return_value = MagicMock(
            id="emp-123",
            org_id="org-1",
            role="employee"  # Not hr_admin
        )

        response = enterprise_client.get(
            "/api/enterprise/compliance/alerts",
            headers=auth_headers
        )

        assert response.status_code == 403

    def test_resolve_compliance_alert(self, enterprise_client, auth_headers, mock_enterprise_service):
        """HR admin can resolve alerts."""
        mock_enterprise_service.get_employee_by_auth_user.return_value = MagicMock(
            id="emp-123",
            org_id="org-1",
            role="hr_admin"
        )
        mock_enterprise_service.resolve_alert.return_value = ComplianceAlertResponse(
            id="alert-1",
            org_id="org-1",
            employee_id="emp-456",
            dept_id=None,
            alert_type="chinese_provider",
            severity="critical",
            provider="deepseek",
            model="deepseek-chat",
            title="Chinese AI Provider Usage Detected",
            message="Employee John used DeepSeek. Data may be stored in China.",
            details={"cost_usd": 0.50},
            resolved=True,
            resolved_by="emp-123",
            resolved_at=datetime.now(timezone.utc),
            resolution_notes="Approved for one-time research use.",
            created_at=datetime.now(timezone.utc)
        )

        response = enterprise_client.post(
            "/api/enterprise/compliance/alerts/alert-1/resolve",
            json={
                "resolution_notes": "Approved for one-time research use."
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["resolved"] is True
        assert data["resolution_notes"] == "Approved for one-time research use."


class TestAPIKeyApproval:
    """Test API key approval workflow (HR admin)."""

    def test_approve_api_key(self, enterprise_client, auth_headers, mock_enterprise_service):
        """HR admin can approve API keys."""
        mock_enterprise_service.get_employee_by_auth_user.return_value = MagicMock(
            id="admin-123",
            org_id="org-1",
            role="hr_admin"
        )
        mock_enterprise_service.approve_api_key.return_value = EmployeeAPIKeyResponse(
            id="key-456",
            employee_id="emp-789",
            provider="anthropic",
            account_type="work",
            key_last_four="xxx1",
            is_approved=True,
            approved_by="admin-123",
            approved_at=datetime.now(timezone.utc),
            data_residency=None,
            compliance_notes="Verified work use case.",
            last_used_at=None,
            total_requests=0,
            total_spend_usd=0.0,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=None
        )

        response = enterprise_client.post(
            "/api/enterprise/api-keys/key-456/approve",
            json={
                "is_approved": True,
                "compliance_notes": "Verified work use case."
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_approved"] is True
        assert data["approved_by"] == "admin-123"

    def test_revoke_api_key(self, enterprise_client, auth_headers, mock_enterprise_service):
        """Admin can revoke API keys."""
        mock_enterprise_service.get_employee_by_auth_user.return_value = MagicMock(
            id="admin-123",
            org_id="org-1",
            role="admin"
        )
        mock_enterprise_service.revoke_api_key.return_value = EmployeeAPIKeyResponse(
            id="key-456",
            employee_id="emp-789",
            provider="anthropic",
            account_type="work",
            key_last_four="xxx1",
            is_approved=True,
            approved_by="admin-123",
            approved_at=datetime.now(timezone.utc),
            data_residency=None,
            compliance_notes=None,
            last_used_at=None,
            total_requests=50,
            total_spend_usd=5.00,
            is_active=False,  # Revoked
            created_at=datetime.now(timezone.utc),
            updated_at=None
        )

        response = enterprise_client.delete(
            "/api/enterprise/api-keys/key-456",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json()["is_active"] is False


class TestChineseProviderCompliance:
    """Test Chinese AI provider compliance features."""

    def test_get_chinese_providers(self, enterprise_client, auth_headers, mock_enterprise_service):
        """List all Chinese AI providers."""
        mock_enterprise_service.get_chinese_providers.return_value = [
            AIProviderInfo(
                id="deepseek",
                display_name="DeepSeek",
                headquarters_country="CN",
                data_residency=["CN"],
                soc2_certified=False,
                hipaa_compliant=False,
                gdpr_compliant=False,
                risk_level="high",
                risk_notes="Chinese company, data stored in China",
                pricing_url="https://platform.deepseek.com/pricing"
            ),
            AIProviderInfo(
                id="qwen",
                display_name="Alibaba Qwen",
                headquarters_country="CN",
                data_residency=["CN"],
                soc2_certified=False,
                hipaa_compliant=False,
                gdpr_compliant=False,
                risk_level="high",
                risk_notes="Chinese company (Alibaba)",
                pricing_url="https://www.alibabacloud.com/product/tongyi"
            )
        ]

        response = enterprise_client.get(
            "/api/enterprise/providers/chinese",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["providers"]) == 2
        assert all(p["headquarters_country"] == "CN" for p in data["providers"])

    def test_check_provider_blocked(self, enterprise_client, auth_headers, mock_enterprise_service):
        """Check if provider is blocked by org policy."""
        mock_enterprise_service.get_employee_by_auth_user.return_value = MagicMock(
            id="emp-123",
            org_id="org-1"
        )
        mock_enterprise_service.is_provider_blocked.return_value = True

        response = enterprise_client.get(
            "/api/enterprise/providers/deepseek/blocked",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json()["is_blocked"] is True
