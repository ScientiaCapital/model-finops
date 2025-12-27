"""
TDD Tests for Enterprise Models (RED Phase)

Test Pydantic models for multi-tenant enterprise schema.
These tests are written BEFORE the implementation (TDD approach).
"""

import pytest
from datetime import datetime, timedelta
from pydantic import ValidationError


class TestAccountTypeEnum:
    """Test AccountType enum for work/personal tracking."""

    def test_account_type_work(self):
        from app.models.enterprise import AccountType
        assert AccountType.WORK.value == "work"

    def test_account_type_personal(self):
        from app.models.enterprise import AccountType
        assert AccountType.PERSONAL.value == "personal"

    def test_account_type_default(self):
        from app.models.enterprise import AccountType
        assert AccountType.DEFAULT.value == "default"


class TestEmployeeRoleEnum:
    """Test EmployeeRole enum for role-based access."""

    def test_employee_role(self):
        from app.models.enterprise import EmployeeRole
        assert EmployeeRole.EMPLOYEE.value == "employee"

    def test_manager_role(self):
        from app.models.enterprise import EmployeeRole
        assert EmployeeRole.MANAGER.value == "manager"

    def test_admin_role(self):
        from app.models.enterprise import EmployeeRole
        assert EmployeeRole.ADMIN.value == "admin"

    def test_hr_admin_role(self):
        from app.models.enterprise import EmployeeRole
        assert EmployeeRole.HR_ADMIN.value == "hr_admin"


class TestRiskLevelEnum:
    """Test RiskLevel enum for compliance."""

    def test_low_risk(self):
        from app.models.enterprise import RiskLevel
        assert RiskLevel.LOW.value == "low"

    def test_high_risk(self):
        from app.models.enterprise import RiskLevel
        assert RiskLevel.HIGH.value == "high"

    def test_blocked_risk(self):
        from app.models.enterprise import RiskLevel
        assert RiskLevel.BLOCKED.value == "blocked"


class TestOrganizationModels:
    """Test Organization create/response models."""

    def test_create_organization_minimal(self):
        from app.models.enterprise import OrganizationCreate
        org = OrganizationCreate(name="Coperniq")
        assert org.name == "Coperniq"
        assert org.domain is None
        assert org.plan == "starter"

    def test_create_organization_with_domain(self):
        from app.models.enterprise import OrganizationCreate
        org = OrganizationCreate(name="Coperniq", domain="coperniq.io")
        assert org.domain == "coperniq.io"

    def test_create_organization_with_settings(self):
        from app.models.enterprise import OrganizationCreate
        settings = {
            "blocked_providers": ["deepseek", "qwen"],
            "max_monthly_budget_usd": 10000,
            "alert_threshold_percent": 80
        }
        org = OrganizationCreate(name="Coperniq", settings=settings)
        assert org.settings["blocked_providers"] == ["deepseek", "qwen"]
        assert org.settings["max_monthly_budget_usd"] == 10000

    def test_create_organization_enterprise_plan(self):
        from app.models.enterprise import OrganizationCreate
        org = OrganizationCreate(name="BigCorp", plan="enterprise")
        assert org.plan == "enterprise"

    def test_organization_name_required(self):
        from app.models.enterprise import OrganizationCreate
        with pytest.raises(ValidationError):
            OrganizationCreate()

    def test_organization_response(self):
        from app.models.enterprise import OrganizationResponse
        org = OrganizationResponse(
            id="org-123",
            name="Coperniq",
            domain="coperniq.io",
            plan="starter",
            settings={},
            created_at=datetime.now()
        )
        assert org.id == "org-123"


class TestEmployeeModels:
    """Test Employee create/response models."""

    def test_create_employee_minimal(self):
        from app.models.enterprise import EmployeeCreate
        emp = EmployeeCreate(email="tim@coperniq.io")
        assert emp.email == "tim@coperniq.io"
        assert emp.role == "employee"

    def test_create_employee_with_name(self):
        from app.models.enterprise import EmployeeCreate
        emp = EmployeeCreate(email="tim@coperniq.io", name="Tim Kipper")
        assert emp.name == "Tim Kipper"

    def test_create_employee_as_manager(self):
        from app.models.enterprise import EmployeeCreate, EmployeeRole
        emp = EmployeeCreate(email="tim@coperniq.io", role=EmployeeRole.MANAGER)
        assert emp.role == "manager"

    def test_create_employee_email_required(self):
        from app.models.enterprise import EmployeeCreate
        with pytest.raises(ValidationError):
            EmployeeCreate()

    def test_employee_with_personal_email(self):
        from app.models.enterprise import EmployeeCreate
        emp = EmployeeCreate(
            email="tim@coperniq.io",
            personal_email="tkipper@gmail.com",
            personal_consent=True
        )
        assert emp.personal_email == "tkipper@gmail.com"
        assert emp.personal_consent is True

    def test_employee_personal_consent_required_for_personal_email(self):
        """Personal email tracking requires GDPR consent."""
        from app.models.enterprise import EmployeeCreate
        emp = EmployeeCreate(
            email="tim@coperniq.io",
            personal_email="tkipper@gmail.com"
        )
        # Default consent is False
        assert emp.personal_consent is False


class TestEmployeeAPIKeyModels:
    """Test Employee API Key create/response models."""

    def test_create_api_key_work(self):
        from app.models.enterprise import EmployeeAPIKeyCreate, AccountType
        key = EmployeeAPIKeyCreate(
            provider="anthropic",
            account_type=AccountType.WORK,
            api_key="sk-ant-api03-xxx"
        )
        assert key.provider == "anthropic"
        assert key.account_type == "work"

    def test_create_api_key_personal(self):
        from app.models.enterprise import EmployeeAPIKeyCreate, AccountType
        key = EmployeeAPIKeyCreate(
            provider="anthropic",
            account_type=AccountType.PERSONAL,
            api_key="sk-ant-api03-personal-xxx"
        )
        assert key.account_type == "personal"

    def test_api_key_required_fields(self):
        from app.models.enterprise import EmployeeAPIKeyCreate
        with pytest.raises(ValidationError):
            EmployeeAPIKeyCreate()

    def test_api_key_response_hides_full_key(self):
        """API key response should only show last 4 chars."""
        from app.models.enterprise import EmployeeAPIKeyResponse
        key = EmployeeAPIKeyResponse(
            id="key-123",
            employee_id="emp-123",
            provider="anthropic",
            account_type="work",
            key_last_four="xxx1",
            is_approved=False,
            is_active=True,
            created_at=datetime.now()
        )
        assert key.key_last_four == "xxx1"
        # Should not have api_key_encrypted field exposed
        assert not hasattr(key, 'api_key_encrypted')


class TestAIProviderInfo:
    """Test AI Provider compliance model."""

    def test_chinese_provider_flagged(self):
        from app.models.enterprise import AIProviderInfo, RiskLevel
        provider = AIProviderInfo(
            id="deepseek",
            display_name="DeepSeek",
            headquarters_country="CN",
            data_residency=["cn"],
            risk_level=RiskLevel.HIGH,
            risk_notes="Chinese company, data stored in China"
        )
        assert provider.is_chinese_company is True
        assert provider.requires_compliance_review is True

    def test_us_provider_not_flagged(self):
        from app.models.enterprise import AIProviderInfo, RiskLevel
        provider = AIProviderInfo(
            id="anthropic",
            display_name="Anthropic Claude",
            headquarters_country="US",
            data_residency=["us"],
            risk_level=RiskLevel.LOW,
            soc2_certified=True
        )
        assert provider.is_chinese_company is False
        assert provider.requires_compliance_review is False

    def test_provider_compliance_flags(self):
        from app.models.enterprise import AIProviderInfo
        provider = AIProviderInfo(
            id="azure-openai",
            display_name="Azure OpenAI",
            headquarters_country="US",
            soc2_certified=True,
            hipaa_compliant=True,
            gdpr_compliant=True
        )
        assert provider.soc2_certified is True
        assert provider.hipaa_compliant is True
        assert provider.gdpr_compliant is True


class TestComplianceAlert:
    """Test Compliance Alert model."""

    def test_create_chinese_provider_alert(self):
        from app.models.enterprise import ComplianceAlert, AlertType, AlertSeverity
        alert = ComplianceAlert(
            org_id="org-123",
            employee_id="emp-123",
            alert_type=AlertType.CHINESE_PROVIDER,
            severity=AlertSeverity.CRITICAL,
            provider="deepseek",
            title="Chinese AI Provider Usage",
            message="Employee used DeepSeek. Data may be stored in China."
        )
        assert alert.alert_type == "chinese_provider"
        assert alert.severity == "critical"

    def test_create_budget_warning_alert(self):
        from app.models.enterprise import ComplianceAlert, AlertType, AlertSeverity
        alert = ComplianceAlert(
            org_id="org-123",
            dept_id="dept-123",
            alert_type=AlertType.BUDGET_WARNING,
            severity=AlertSeverity.WARNING,
            title="Department Budget Warning",
            message="Engineering at 85% of monthly budget"
        )
        assert alert.alert_type == "budget_warning"
        assert alert.severity == "warning"


class TestUsageLogEntry:
    """Test Usage Log Entry model."""

    def test_create_usage_entry(self):
        from app.models.enterprise import UsageLogEntry
        entry = UsageLogEntry(
            employee_id="emp-123",
            provider="anthropic",
            model="claude-3-opus",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=0.05,
            account_type="work"
        )
        assert entry.total_tokens == 1500
        assert entry.cost_usd == 0.05

    def test_usage_entry_flagged(self):
        from app.models.enterprise import UsageLogEntry
        entry = UsageLogEntry(
            employee_id="emp-123",
            provider="deepseek",
            model="deepseek-chat",
            input_tokens=100,
            output_tokens=100,
            cost_usd=0.001,
            account_type="personal",
            flagged_for_review=True,
            flag_reason="Chinese provider"
        )
        assert entry.flagged_for_review is True
        assert "Chinese" in entry.flag_reason


class TestLinkPersonalAccount:
    """Test personal account linking models."""

    def test_link_personal_request(self):
        from app.models.enterprise import LinkPersonalAccountRequest
        req = LinkPersonalAccountRequest(
            personal_email="tkipper@gmail.com",
            consent_given=True
        )
        assert req.personal_email == "tkipper@gmail.com"
        assert req.consent_given is True

    def test_link_personal_requires_consent(self):
        from app.models.enterprise import LinkPersonalAccountRequest
        with pytest.raises(ValidationError) as exc_info:
            LinkPersonalAccountRequest(
                personal_email="tkipper@gmail.com",
                consent_given=False  # Must be True for GDPR
            )
        assert "consent" in str(exc_info.value).lower()


class TestDepartmentModels:
    """Test Department models."""

    def test_create_department(self):
        from app.models.enterprise import DepartmentCreate
        dept = DepartmentCreate(name="Engineering", budget_usd=10000.00)
        assert dept.name == "Engineering"
        assert dept.budget_usd == 10000.00

    def test_department_response(self):
        from app.models.enterprise import DepartmentResponse
        dept = DepartmentResponse(
            id="dept-123",
            org_id="org-123",
            name="Engineering",
            budget_usd=10000.00,
            created_at=datetime.now()
        )
        assert dept.id == "dept-123"


class TestSpendSummary:
    """Test spend summary models for analytics."""

    def test_department_spend_summary(self):
        from app.models.enterprise import DepartmentSpendSummary
        summary = DepartmentSpendSummary(
            department_name="Engineering",
            total_spend_usd=8500.00,
            budget_usd=10000.00,
            budget_percent=85.0,
            employee_count=15,
            top_provider="anthropic"
        )
        assert summary.budget_percent == 85.0
        assert summary.is_over_threshold(80) is True
        assert summary.is_over_threshold(90) is False

    def test_employee_spend_summary(self):
        from app.models.enterprise import EmployeeSpendSummary
        summary = EmployeeSpendSummary(
            employee_name="Tim Kipper",
            email="tim@coperniq.io",
            work_spend_usd=150.00,
            personal_spend_usd=50.00
        )
        assert summary.total_spend_usd == 200.00
