"""
Enterprise Service

Business logic for multi-tenant organizations, employees, API keys, and compliance.
Handles work/personal account separation and Chinese AI model flagging.

Architecture:
- Uses Supabase client for database operations
- Uses EncryptionService for API key encryption
- Returns Pydantic models for type safety
- Async-first design for performance
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from app.models.enterprise import (
    OrganizationCreate, OrganizationResponse,
    EmployeeCreate, EmployeeResponse, EmployeeSpendSummary,
    EmployeeAPIKeyCreate, EmployeeAPIKeyResponse,
    DepartmentCreate, DepartmentResponse, DepartmentSpendSummary,
    AIProviderInfo, ComplianceAlert, ComplianceAlertResponse,
    UsageLogEntry, UsageLogResponse,
    AlertType, AlertSeverity
)
from app.services.encryption_service import EncryptionService, get_encryption_service


class EnterpriseService:
    """
    Enterprise service for multi-tenant AI cost management.

    Handles:
    - Organization and department management
    - Employee onboarding with personal account linking
    - API key management with encryption
    - Usage logging and compliance alerts
    - Spend analytics by department and employee
    """

    def __init__(self, supabase_client=None, encryption_service=None):
        """
        Initialize enterprise service.

        Args:
            supabase_client: Supabase client instance (or mock for testing)
            encryption_service: Encryption service for API keys
        """
        self._supabase = supabase_client
        self._encryption = encryption_service or get_encryption_service()

    @property
    def supabase(self):
        """Lazy load Supabase client."""
        if self._supabase is None:
            from app.database.supabase_client import get_supabase_client
            self._supabase = get_supabase_client()
        return self._supabase

    # =========================================================================
    # Organization Management
    # =========================================================================

    async def create_organization(
        self,
        name: str,
        domain: Optional[str] = None,
        plan: str = "starter",
        settings: Optional[Dict[str, Any]] = None
    ) -> OrganizationResponse:
        """
        Create a new organization.

        Args:
            name: Organization name
            domain: Domain for SSO matching (e.g., "coperniq.io")
            plan: Subscription plan (starter, growth, enterprise)
            settings: AI policy settings (blocked providers, budgets, etc.)

        Returns:
            Created organization
        """
        data = {
            "name": name,
            "domain": domain,
            "plan": plan,
            "settings": settings or {}
        }

        result = self.supabase.table("organizations").insert(data).execute()

        if result.data:
            return OrganizationResponse(**result.data[0])
        raise ValueError("Failed to create organization")

    async def get_organization(self, org_id: str) -> Optional[OrganizationResponse]:
        """Get organization by ID."""
        result = self.supabase.table("organizations").select("*").eq("id", org_id).execute()

        if result.data:
            return OrganizationResponse(**result.data[0])
        return None

    async def update_organization_settings(
        self,
        org_id: str,
        settings: Dict[str, Any]
    ) -> OrganizationResponse:
        """Update organization AI policy settings."""
        result = self.supabase.table("organizations").update({
            "settings": settings
        }).eq("id", org_id).execute()

        if result.data:
            return OrganizationResponse(**result.data[0])
        raise ValueError("Organization not found")

    # =========================================================================
    # Employee Management
    # =========================================================================

    async def add_employee(
        self,
        org_id: str,
        email: str,
        name: Optional[str] = None,
        role: str = "employee",
        dept_id: Optional[str] = None,
        auth_user_id: Optional[str] = None
    ) -> EmployeeResponse:
        """
        Add employee to organization.

        Args:
            org_id: Organization ID
            email: Work email address
            name: Employee name
            role: Role (employee, manager, admin, hr_admin)
            dept_id: Department ID
            auth_user_id: Supabase Auth user ID for linking

        Returns:
            Created employee record
        """
        data = {
            "org_id": org_id,
            "email": email,
            "name": name,
            "role": role,
            "dept_id": dept_id,
            "auth_user_id": auth_user_id,
            "is_active": True
        }

        result = self.supabase.table("employees").insert(data).execute()

        if result.data:
            return EmployeeResponse(**result.data[0])
        raise ValueError("Failed to add employee")

    async def get_employee(self, employee_id: str) -> Optional[EmployeeResponse]:
        """Get employee by ID."""
        result = self.supabase.table("employees").select("*").eq("id", employee_id).execute()

        if result.data:
            return EmployeeResponse(**result.data[0])
        return None

    async def get_employee_by_auth_user(self, auth_user_id: str) -> Optional[EmployeeResponse]:
        """Get employee by Supabase Auth user ID."""
        result = self.supabase.table("employees").select("*").eq("auth_user_id", auth_user_id).execute()

        if result.data:
            return EmployeeResponse(**result.data[0])
        return None

    async def link_personal_account(
        self,
        employee_id: str,
        personal_email: str,
        consent: bool
    ) -> EmployeeResponse:
        """
        Link personal email for expense tracking.

        Requires explicit GDPR consent.

        Args:
            employee_id: Employee ID
            personal_email: Personal email address
            consent: GDPR consent (must be True)

        Returns:
            Updated employee record

        Raises:
            ValueError: If consent is not given
        """
        if not consent:
            raise ValueError("GDPR consent is required to link personal account")

        result = self.supabase.table("employees").update({
            "personal_email": personal_email,
            "personal_consent": True,
            "personal_consent_date": datetime.now(timezone.utc).isoformat(),
            "personal_linked_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", employee_id).execute()

        if result.data:
            return EmployeeResponse(**result.data[0])
        raise ValueError("Employee not found")

    # =========================================================================
    # API Key Management
    # =========================================================================

    async def add_employee_api_key(
        self,
        employee_id: str,
        provider: str,
        api_key: str,
        account_type: str = "work",
        data_residency: Optional[str] = None,
        compliance_notes: Optional[str] = None
    ) -> EmployeeAPIKeyResponse:
        """
        Add an API key for an employee.

        The key is encrypted before storage.

        Args:
            employee_id: Employee ID
            provider: Provider name (anthropic, openai, etc.)
            api_key: Raw API key (will be encrypted)
            account_type: work or personal
            data_residency: Override data residency if known
            compliance_notes: Notes for compliance review

        Returns:
            API key record (without the encrypted key)
        """
        # Encrypt the API key
        encrypted_key = self._encryption.encrypt(api_key)
        key_last_four = self._encryption.get_key_last_four(api_key)

        data = {
            "employee_id": employee_id,
            "provider": provider,
            "account_type": account_type,
            "api_key_encrypted": encrypted_key,
            "key_last_four": key_last_four,
            "encryption_version": 1,
            "data_residency": data_residency,
            "compliance_notes": compliance_notes,
            "is_approved": False,
            "is_active": True
        }

        result = self.supabase.table("employee_api_keys").insert(data).execute()

        if result.data:
            return EmployeeAPIKeyResponse(**result.data[0])
        raise ValueError("Failed to add API key")

    async def get_employee_api_keys(
        self,
        employee_id: str,
        include_inactive: bool = False
    ) -> List[EmployeeAPIKeyResponse]:
        """Get all API keys for an employee."""
        query = self.supabase.table("employee_api_keys").select("*").eq("employee_id", employee_id)

        if not include_inactive:
            query = query.eq("is_active", True)

        result = query.execute()

        return [EmployeeAPIKeyResponse(**k) for k in result.data]

    async def approve_api_key(
        self,
        key_id: str,
        approved_by: str,
        notes: Optional[str] = None
    ) -> EmployeeAPIKeyResponse:
        """Approve an API key (HR admin action)."""
        result = self.supabase.table("employee_api_keys").update({
            "is_approved": True,
            "approved_by": approved_by,
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "compliance_notes": notes
        }).eq("id", key_id).execute()

        if result.data:
            return EmployeeAPIKeyResponse(**result.data[0])
        raise ValueError("API key not found")

    async def revoke_api_key(
        self,
        key_id: str,
        revoked_by: str,
        reason: Optional[str] = None
    ) -> EmployeeAPIKeyResponse:
        """Revoke an API key."""
        result = self.supabase.table("employee_api_keys").update({
            "is_active": False,
            "revoked_at": datetime.now(timezone.utc).isoformat(),
            "revoked_by": revoked_by,
            "revoke_reason": reason
        }).eq("id", key_id).execute()

        if result.data:
            return EmployeeAPIKeyResponse(**result.data[0])
        raise ValueError("API key not found")

    async def decrypt_api_key(self, key_id: str) -> str:
        """
        Decrypt an API key for use.

        WARNING: Only call this when actively using the key.
        Never log or expose the decrypted key.
        """
        result = self.supabase.table("employee_api_keys").select(
            "api_key_encrypted"
        ).eq("id", key_id).eq("is_active", True).execute()

        if not result.data:
            raise ValueError("API key not found or inactive")

        return self._encryption.decrypt(result.data[0]["api_key_encrypted"])

    # =========================================================================
    # Usage Logging
    # =========================================================================

    async def log_usage(
        self,
        employee_id: str,
        provider: str,
        model: Optional[str] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
        account_type: str = "work",
        api_key_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        latency_ms: Optional[int] = None
    ) -> UsageLogEntry:
        """
        Log AI usage for tracking and analytics.

        Args:
            employee_id: Employee ID
            provider: Provider name
            model: Model name
            input_tokens: Input token count
            output_tokens: Output token count
            cost_usd: Cost in USD
            account_type: work or personal
            api_key_id: API key used (if known)
            endpoint: API endpoint
            latency_ms: Request latency

        Returns:
            Usage log entry
        """
        data = {
            "employee_id": employee_id,
            "provider": provider,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
            "account_type": account_type,
            "api_key_id": api_key_id,
            "endpoint": endpoint,
            "latency_ms": latency_ms,
            "flagged_for_review": False
        }

        result = self.supabase.table("ai_usage_log").insert(data).execute()

        if result.data:
            entry = result.data[0]
            return UsageLogEntry(
                employee_id=entry["employee_id"],
                provider=entry["provider"],
                model=entry.get("model"),
                input_tokens=entry.get("input_tokens", 0),
                output_tokens=entry.get("output_tokens", 0),
                cost_usd=entry.get("cost_usd", 0),
                account_type=entry.get("account_type"),
                flagged_for_review=entry.get("flagged_for_review", False)
            )
        raise ValueError("Failed to log usage")

    async def log_usage_with_compliance(
        self,
        employee_id: str,
        org_id: str,
        provider: str,
        model: Optional[str] = None,
        cost_usd: float = 0.0,
        **kwargs
    ) -> List[ComplianceAlert]:
        """
        Log usage and check for compliance issues.

        Returns any compliance alerts generated.
        """
        alerts = []

        # Check if provider is Chinese
        provider_info = await self.get_provider_info(provider)
        if provider_info and provider_info.is_chinese_company:
            # Get employee info for alert
            emp = await self.get_employee(employee_id)
            emp_name = emp.name if emp else "Unknown"

            alert = ComplianceAlert(
                org_id=org_id,
                employee_id=employee_id,
                alert_type=AlertType.CHINESE_PROVIDER.value,
                severity=AlertSeverity.CRITICAL.value,
                provider=provider,
                model=model,
                title="Chinese AI Provider Usage Detected",
                message=f"Employee {emp_name} used {provider}. Data may be stored in China.",
                details={"cost_usd": cost_usd}
            )
            alerts.append(alert)

            # Create alert in database
            await self._create_alert(alert)

        # Log the usage
        await self.log_usage(
            employee_id=employee_id,
            provider=provider,
            model=model,
            cost_usd=cost_usd,
            **kwargs
        )

        return alerts

    async def check_budget_compliance(
        self,
        dept_id: str,
        threshold_percent: float = 80.0
    ) -> List[ComplianceAlert]:
        """Check if department is over budget threshold."""
        alerts = []

        # Get department spend
        result = self.supabase.rpc("get_department_spend", {"dept_id": dept_id}).execute()

        if result.data:
            spend_data = result.data[0] if isinstance(result.data, list) else result.data
            budget_percent = spend_data.get("budget_percent", 0)

            if budget_percent >= threshold_percent:
                alert = ComplianceAlert(
                    org_id="",  # Will be filled from dept lookup
                    dept_id=dept_id,
                    alert_type=AlertType.BUDGET_WARNING.value,
                    severity=AlertSeverity.WARNING.value,
                    title="Department Budget Warning",
                    message=f"Department at {budget_percent}% of monthly budget",
                    details={"budget_percent": budget_percent}
                )
                alerts.append(alert)

        return alerts

    # =========================================================================
    # Compliance Alerts
    # =========================================================================

    async def _create_alert(self, alert: ComplianceAlert) -> ComplianceAlertResponse:
        """Create a compliance alert in the database."""
        data = {
            "org_id": alert.org_id,
            "employee_id": alert.employee_id,
            "dept_id": alert.dept_id,
            "alert_type": alert.alert_type,
            "severity": alert.severity,
            "provider": alert.provider,
            "model": alert.model,
            "title": alert.title,
            "message": alert.message,
            "details": alert.details,
            "resolved": False
        }

        result = self.supabase.table("compliance_alerts").insert(data).execute()

        if result.data:
            return ComplianceAlertResponse(**result.data[0])
        raise ValueError("Failed to create alert")

    async def get_compliance_alerts(
        self,
        org_id: str,
        resolved: Optional[bool] = None,
        alert_type: Optional[str] = None,
        limit: int = 100
    ) -> List[ComplianceAlertResponse]:
        """Get compliance alerts for organization."""
        query = self.supabase.table("compliance_alerts").select("*").eq("org_id", org_id)

        if resolved is not None:
            query = query.eq("resolved", resolved)
        if alert_type:
            query = query.eq("alert_type", alert_type)

        query = query.order("created_at", desc=True).limit(limit)
        result = query.execute()

        return [ComplianceAlertResponse(**a) for a in result.data]

    async def resolve_alert(
        self,
        alert_id: str,
        resolved_by: str,
        notes: Optional[str] = None
    ) -> ComplianceAlertResponse:
        """Resolve a compliance alert."""
        result = self.supabase.table("compliance_alerts").update({
            "resolved": True,
            "resolved_by": resolved_by,
            "resolved_at": datetime.now(timezone.utc).isoformat(),
            "resolution_notes": notes
        }).eq("id", alert_id).execute()

        if result.data:
            return ComplianceAlertResponse(**result.data[0])
        raise ValueError("Alert not found")

    # =========================================================================
    # Analytics
    # =========================================================================

    async def get_department_spend(self, dept_id: str) -> DepartmentSpendSummary:
        """Get spend summary for a department."""
        result = self.supabase.rpc("get_department_spend", {"dept_id": dept_id}).execute()

        if result.data:
            data = result.data[0] if isinstance(result.data, list) else result.data
            budget = data.get("budget_usd", 0) or 0
            spend = data.get("total_spend", 0) or 0

            return DepartmentSpendSummary(
                department_name=data.get("department_name", "Unknown"),
                total_spend_usd=spend,
                budget_usd=budget,
                budget_percent=round(spend / budget * 100, 1) if budget > 0 else 0,
                employee_count=data.get("employee_count", 0),
                top_provider=data.get("top_provider")
            )
        raise ValueError("Department not found")

    async def get_employee_spend(self, employee_id: str) -> EmployeeSpendSummary:
        """Get spend summary for an employee (work vs personal)."""
        result = self.supabase.table("ai_usage_log").select(
            "account_type, cost_usd"
        ).eq("employee_id", employee_id).execute()

        work_spend = 0.0
        personal_spend = 0.0

        for entry in result.data:
            cost = entry.get("cost_usd", 0) or 0
            if entry.get("account_type") == "personal":
                personal_spend += cost
            else:
                work_spend += cost

        # Get employee info
        emp = await self.get_employee(employee_id)

        return EmployeeSpendSummary(
            employee_name=emp.name if emp else None,
            email=emp.email if emp else "",
            work_spend_usd=work_spend,
            personal_spend_usd=personal_spend
        )

    async def get_org_spend_by_department(self, org_id: str) -> List[DepartmentSpendSummary]:
        """Get spend breakdown by department for an organization."""
        result = self.supabase.table("departments").select(
            "id, name, budget_usd"
        ).eq("org_id", org_id).execute()

        summaries = []
        for dept in result.data:
            try:
                summary = await self.get_department_spend(dept["id"])
                summary.department_name = dept["name"]
                summaries.append(summary)
            except Exception:
                # If no spend data, create empty summary
                summaries.append(DepartmentSpendSummary(
                    department_name=dept["name"],
                    total_spend_usd=0,
                    budget_usd=dept.get("budget_usd", 0)
                ))

        return summaries

    # =========================================================================
    # Provider Compliance
    # =========================================================================

    async def get_provider_info(self, provider_id: str) -> Optional[AIProviderInfo]:
        """Get provider compliance information."""
        result = self.supabase.table("ai_providers").select("*").eq("id", provider_id).execute()

        if result.data:
            return AIProviderInfo(**result.data[0])
        return None

    async def is_provider_blocked(self, org_id: str, provider: str) -> bool:
        """Check if provider is blocked by organization policy."""
        org = await self.get_organization(org_id)
        if not org:
            return False

        blocked = org.settings.get("blocked_providers", [])
        return provider in blocked

    async def get_chinese_providers(self) -> List[AIProviderInfo]:
        """Get all Chinese AI providers."""
        result = self.supabase.table("ai_providers").select("*").eq(
            "headquarters_country", "CN"
        ).execute()

        return [AIProviderInfo(**p) for p in result.data]


# Singleton instance
_enterprise_service: Optional[EnterpriseService] = None


def get_enterprise_service() -> EnterpriseService:
    """Get the enterprise service instance."""
    global _enterprise_service
    if _enterprise_service is None:
        _enterprise_service = EnterpriseService()
    return _enterprise_service
