"""
Enterprise Multi-Tenant Models

Pydantic models for organizations, employees, API keys, and compliance tracking.
Supports work/personal account separation and Chinese AI model flagging.

Security Notes:
- API keys are stored encrypted (AES-256-GCM)
- Only key_last_four is exposed in responses
- Personal email linking requires explicit GDPR consent
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, computed_field, field_validator

# =============================================================================
# Enums
# =============================================================================


class AccountType(StrEnum):
    """Account type for API key ownership."""

    WORK = "work"
    PERSONAL = "personal"
    DEFAULT = "default"


class EmployeeRole(StrEnum):
    """Employee role for access control."""

    EMPLOYEE = "employee"
    MANAGER = "manager"
    ADMIN = "admin"
    HR_ADMIN = "hr_admin"


class RiskLevel(StrEnum):
    """Provider risk level for compliance."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKED = "blocked"


class AlertType(StrEnum):
    """Types of compliance alerts."""

    BLOCKED_PROVIDER = "blocked_provider"
    CHINESE_PROVIDER = "chinese_provider"
    UNAPPROVED_MODEL = "unapproved_model"
    BUDGET_WARNING = "budget_warning"
    BUDGET_EXCEEDED = "budget_exceeded"
    PERSONAL_HIGH_USAGE = "personal_high_usage"
    DATA_RESIDENCY = "data_residency"
    NEW_API_KEY = "new_api_key"


class AlertSeverity(StrEnum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


# =============================================================================
# Organization Models
# =============================================================================


class OrganizationCreate(BaseModel):
    """Request model for creating an organization."""

    name: str = Field(..., min_length=1, max_length=200)
    domain: str | None = Field(None, max_length=200)
    plan: str = Field(default="starter")
    settings: dict[str, Any] = Field(default_factory=dict)

    @field_validator("plan")
    @classmethod
    def validate_plan(cls, v: str) -> str:
        valid_plans = ["starter", "growth", "enterprise"]
        if v not in valid_plans:
            raise ValueError(f"Plan must be one of: {valid_plans}")
        return v


class OrganizationResponse(BaseModel):
    """Response model for organization."""

    id: str
    name: str
    domain: str | None = None
    plan: str
    settings: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime | None = None


class OrganizationUpdate(BaseModel):
    """Request model for updating organization settings."""

    name: str | None = None
    settings: dict[str, Any] | None = None
    plan: str | None = None


# =============================================================================
# Department Models
# =============================================================================


class DepartmentCreate(BaseModel):
    """Request model for creating a department."""

    name: str = Field(..., min_length=1, max_length=200)
    budget_usd: float | None = Field(None, ge=0)
    manager_id: str | None = None


class DepartmentResponse(BaseModel):
    """Response model for department."""

    id: str
    org_id: str
    name: str
    budget_usd: float | None = None
    manager_id: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class DepartmentSpendSummary(BaseModel):
    """Summary of department AI spend."""

    department_name: str
    total_spend_usd: float = 0.0
    budget_usd: float | None = None
    budget_percent: float = 0.0
    employee_count: int = 0
    top_provider: str | None = None

    def is_over_threshold(self, threshold_percent: float) -> bool:
        """Check if spend is over a percentage threshold."""
        return self.budget_percent >= threshold_percent


# =============================================================================
# Employee Models
# =============================================================================


class EmployeeCreate(BaseModel):
    """Request model for creating/inviting an employee."""

    email: str = Field(..., min_length=1, max_length=200)
    name: str | None = Field(None, max_length=200)
    role: str = Field(default="employee")
    dept_id: str | None = None
    personal_email: str | None = Field(None, max_length=200)
    personal_consent: bool = Field(default=False)

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if isinstance(v, EmployeeRole):
            return v.value
        valid_roles = [r.value for r in EmployeeRole]
        if v not in valid_roles:
            raise ValueError(f"Role must be one of: {valid_roles}")
        return v


class EmployeeResponse(BaseModel):
    """Response model for employee."""

    id: str
    org_id: str
    dept_id: str | None = None
    email: str
    name: str | None = None
    role: str
    personal_email: str | None = None
    personal_linked_at: datetime | None = None
    personal_consent: bool = False
    is_active: bool = True
    created_at: datetime
    updated_at: datetime | None = None


class EmployeeSpendSummary(BaseModel):
    """Summary of employee AI spend."""

    employee_name: str | None = None
    email: str = ""
    work_spend_usd: float = 0.0
    personal_spend_usd: float = 0.0

    @computed_field
    @property
    def total_spend_usd(self) -> float:
        """Total spend across work and personal accounts."""
        return self.work_spend_usd + self.personal_spend_usd


class LinkPersonalAccountRequest(BaseModel):
    """Request to link personal email for expense tracking."""

    personal_email: str = Field(..., min_length=1, max_length=200)
    consent_given: bool = Field(...)

    @field_validator("consent_given")
    @classmethod
    def validate_consent(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("GDPR consent must be explicitly given (consent_given=true)")
        return v


# =============================================================================
# Employee API Key Models
# =============================================================================


class EmployeeAPIKeyCreate(BaseModel):
    """Request model for adding an API key."""

    provider: str = Field(..., min_length=1, max_length=50)
    account_type: str = Field(...)
    api_key: str = Field(..., min_length=1)
    data_residency: str | None = None
    compliance_notes: str | None = None

    @field_validator("account_type")
    @classmethod
    def validate_account_type(cls, v: str) -> str:
        if isinstance(v, AccountType):
            return v.value
        valid_types = [t.value for t in AccountType]
        if v not in valid_types:
            raise ValueError(f"Account type must be one of: {valid_types}")
        return v


class EmployeeAPIKeyResponse(BaseModel):
    """Response model for API key (never exposes full key)."""

    id: str
    employee_id: str
    provider: str
    account_type: str
    key_last_four: str
    is_approved: bool = False
    approved_by: str | None = None
    approved_at: datetime | None = None
    data_residency: str | None = None
    compliance_notes: str | None = None
    last_used_at: datetime | None = None
    total_requests: int = 0
    total_spend_usd: float = 0.0
    is_active: bool = True
    created_at: datetime
    updated_at: datetime | None = None


class EmployeeAPIKeyApproval(BaseModel):
    """Request to approve/reject an API key."""

    is_approved: bool
    compliance_notes: str | None = None


# =============================================================================
# AI Provider Models
# =============================================================================


class AIProviderInfo(BaseModel):
    """AI provider with compliance metadata."""

    id: str
    display_name: str = ""
    headquarters_country: str | None = None
    data_residency: list[str] = Field(default_factory=list)
    soc2_certified: bool = False
    hipaa_compliant: bool = False
    gdpr_compliant: bool = False
    risk_level: str = "medium"
    risk_notes: str | None = None
    pricing_url: str | None = None

    @computed_field
    @property
    def is_chinese_company(self) -> bool:
        """Check if provider is headquartered in China."""
        return self.headquarters_country == "CN"

    @computed_field
    @property
    def requires_compliance_review(self) -> bool:
        """Check if provider requires compliance review."""
        if isinstance(self.risk_level, RiskLevel):
            return self.risk_level in [RiskLevel.HIGH, RiskLevel.BLOCKED]
        return self.risk_level in ["high", "blocked"]


# =============================================================================
# Compliance Alert Models
# =============================================================================


class ComplianceAlert(BaseModel):
    """Compliance alert for HR/Admin review."""

    org_id: str
    employee_id: str | None = None
    dept_id: str | None = None
    alert_type: str
    severity: str = "warning"
    provider: str | None = None
    model: str | None = None
    title: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    resolved: bool = False
    resolved_by: str | None = None
    resolved_at: datetime | None = None
    resolution_notes: str | None = None
    created_at: datetime | None = None

    @field_validator("alert_type")
    @classmethod
    def validate_alert_type(cls, v: str) -> str:
        if isinstance(v, AlertType):
            return v.value
        valid_types = [t.value for t in AlertType]
        if v not in valid_types:
            raise ValueError(f"Alert type must be one of: {valid_types}")
        return v

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        if isinstance(v, AlertSeverity):
            return v.value
        valid = [s.value for s in AlertSeverity]
        if v not in valid:
            raise ValueError(f"Severity must be one of: {valid}")
        return v


class ComplianceAlertResponse(BaseModel):
    """Response model for compliance alert."""

    id: str
    org_id: str
    employee_id: str | None = None
    dept_id: str | None = None
    alert_type: str
    severity: str
    provider: str | None = None
    model: str | None = None
    title: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    resolved: bool = False
    resolved_by: str | None = None
    resolved_at: datetime | None = None
    resolution_notes: str | None = None
    created_at: datetime


class ResolveAlertRequest(BaseModel):
    """Request to resolve a compliance alert."""

    resolution_notes: str | None = Field(None, max_length=1000)


# =============================================================================
# Usage Log Models
# =============================================================================


class UsageLogEntry(BaseModel):
    """AI usage log entry."""

    employee_id: str
    api_key_id: str | None = None
    provider: str
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int | None = None
    account_type: str | None = None
    endpoint: str | None = None
    request_metadata: dict[str, Any] = Field(default_factory=dict)
    flagged_for_review: bool = False
    flag_reason: str | None = None
    created_at: datetime | None = None

    @computed_field
    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.input_tokens + self.output_tokens


class UsageLogResponse(BaseModel):
    """Response model for usage log entry."""

    id: str
    employee_id: str
    api_key_id: str | None = None
    provider: str
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int | None = None
    account_type: str | None = None
    flagged_for_review: bool = False
    flag_reason: str | None = None
    created_at: datetime


# =============================================================================
# Analytics Models
# =============================================================================


class ProviderUsageSummary(BaseModel):
    """Usage summary by provider."""

    provider: str
    display_name: str = ""
    total_requests: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    risk_level: str = "medium"
    is_chinese: bool = False


class ComplianceSummary(BaseModel):
    """Organization-wide compliance summary."""

    total_alerts: int = 0
    critical_unresolved: int = 0
    chinese_usage_count: int = 0
    budget_warnings: int = 0
    last_updated: datetime | None = None
