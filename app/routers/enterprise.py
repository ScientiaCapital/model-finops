"""
Enterprise Multi-Tenant Router

REST API endpoints for enterprise features:
- Organization management
- Employee API key management (work/personal)
- Personal account linking with GDPR consent
- Compliance alerts for Chinese AI providers
- Spend analytics by department

All endpoints require JWT authentication.
Role-based access control:
- employee: Can manage own API keys and usage
- manager: Can view team usage
- hr_admin: Can view compliance alerts and org spend
- admin: Can manage organization settings
"""

import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.models.enterprise import (
    OrganizationCreate, OrganizationResponse, OrganizationUpdate,
    EmployeeCreate, EmployeeResponse, EmployeeSpendSummary,
    EmployeeAPIKeyCreate, EmployeeAPIKeyResponse,
    DepartmentSpendSummary,
    LinkPersonalAccountRequest,
    ComplianceAlertResponse, ResolveAlertRequest,
    EmployeeAPIKeyApproval, AIProviderInfo
)
from app.services.enterprise_service import EnterpriseService, get_enterprise_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/enterprise",
    tags=["enterprise"],
)


# =============================================================================
# Response Models
# =============================================================================

class APIKeyListResponse(BaseModel):
    """List of API keys."""
    keys: List[EmployeeAPIKeyResponse]


class AlertListResponse(BaseModel):
    """List of compliance alerts."""
    alerts: List[ComplianceAlertResponse]


class DepartmentSpendListResponse(BaseModel):
    """List of department spend summaries."""
    departments: List[DepartmentSpendSummary]


class ProviderListResponse(BaseModel):
    """List of AI providers."""
    providers: List[AIProviderInfo]


class ProviderBlockedResponse(BaseModel):
    """Provider blocked status."""
    provider: str
    is_blocked: bool


# =============================================================================
# Helper: Role-based access control
# =============================================================================

async def require_role(
    user_id: str,
    required_roles: List[str],
    service: EnterpriseService
) -> EmployeeResponse:
    """Check if user has required role."""
    employee = await service.get_employee_by_auth_user(user_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not found in organization"
        )

    if employee.role not in required_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires one of: {', '.join(required_roles)}"
        )

    return employee


# =============================================================================
# Organization Endpoints
# =============================================================================

@router.post(
    "/organizations",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create organization"
)
async def create_organization(
    request: OrganizationCreate,
    user_id: str = Depends(get_current_user_id),
    service: EnterpriseService = Depends(get_enterprise_service),
):
    """Create a new organization. Requires admin role."""
    try:
        return await service.create_organization(
            name=request.name,
            domain=request.domain,
            plan=request.plan,
            settings=request.settings
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/organizations/{org_id}",
    response_model=OrganizationResponse,
    summary="Get organization"
)
async def get_organization(
    org_id: str,
    user_id: str = Depends(get_current_user_id),
    service: EnterpriseService = Depends(get_enterprise_service),
):
    """Get organization details."""
    org = await service.get_organization(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.patch(
    "/organizations/{org_id}",
    response_model=OrganizationResponse,
    summary="Update organization settings"
)
async def update_organization(
    org_id: str,
    request: OrganizationUpdate,
    user_id: str = Depends(get_current_user_id),
    service: EnterpriseService = Depends(get_enterprise_service),
):
    """Update organization AI policy settings. Requires admin role."""
    try:
        return await service.update_organization_settings(org_id, request.settings)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# =============================================================================
# Employee API Key Endpoints
# =============================================================================

@router.post(
    "/employees/me/api-keys",
    response_model=EmployeeAPIKeyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add my API key"
)
async def add_my_api_key(
    request: EmployeeAPIKeyCreate,
    user_id: str = Depends(get_current_user_id),
    service: EnterpriseService = Depends(get_enterprise_service),
):
    """Add an API key for the authenticated employee."""
    employee = await service.get_employee_by_auth_user(user_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    try:
        return await service.add_employee_api_key(
            employee_id=employee.id,
            provider=request.provider,
            api_key=request.api_key,
            account_type=request.account_type,
            data_residency=request.data_residency,
            compliance_notes=request.compliance_notes
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/employees/me/api-keys",
    response_model=APIKeyListResponse,
    summary="List my API keys"
)
async def list_my_api_keys(
    include_inactive: bool = Query(False, description="Include revoked keys"),
    user_id: str = Depends(get_current_user_id),
    service: EnterpriseService = Depends(get_enterprise_service),
):
    """List all API keys for the authenticated employee."""
    employee = await service.get_employee_by_auth_user(user_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    keys = await service.get_employee_api_keys(employee.id, include_inactive)
    return APIKeyListResponse(keys=keys)


# =============================================================================
# Personal Account Linking
# =============================================================================

@router.post(
    "/employees/me/link-personal",
    response_model=EmployeeResponse,
    summary="Link personal account"
)
async def link_personal_account(
    request: LinkPersonalAccountRequest,
    user_id: str = Depends(get_current_user_id),
    service: EnterpriseService = Depends(get_enterprise_service),
):
    """
    Link personal email for expense tracking.

    Requires explicit GDPR consent (consent_given=true).
    """
    employee = await service.get_employee_by_auth_user(user_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    try:
        return await service.link_personal_account(
            employee_id=employee.id,
            personal_email=request.personal_email,
            consent=request.consent_given
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Usage Endpoints
# =============================================================================

@router.get(
    "/employees/me/usage",
    response_model=EmployeeSpendSummary,
    summary="Get my usage"
)
async def get_my_usage(
    user_id: str = Depends(get_current_user_id),
    service: EnterpriseService = Depends(get_enterprise_service),
):
    """Get usage summary for the authenticated employee."""
    employee = await service.get_employee_by_auth_user(user_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    return await service.get_employee_spend(employee.id)


@router.get(
    "/team/usage",
    response_model=DepartmentSpendSummary,
    summary="Get team usage (manager only)"
)
async def get_team_usage(
    user_id: str = Depends(get_current_user_id),
    service: EnterpriseService = Depends(get_enterprise_service),
):
    """Get department usage summary. Requires manager, admin, or hr_admin role."""
    employee = await require_role(
        user_id,
        ["manager", "admin", "hr_admin"],
        service
    )

    if not employee.dept_id:
        raise HTTPException(status_code=400, detail="Not assigned to a department")

    return await service.get_department_spend(employee.dept_id)


@router.get(
    "/org/spend-by-department",
    response_model=DepartmentSpendListResponse,
    summary="Get org spend by department (HR admin only)"
)
async def get_org_spend_by_department(
    user_id: str = Depends(get_current_user_id),
    service: EnterpriseService = Depends(get_enterprise_service),
):
    """Get spend breakdown by department. Requires hr_admin role."""
    employee = await require_role(user_id, ["hr_admin", "admin"], service)

    departments = await service.get_org_spend_by_department(employee.org_id)
    return DepartmentSpendListResponse(departments=departments)


# =============================================================================
# Compliance Alert Endpoints
# =============================================================================

@router.get(
    "/compliance/alerts",
    response_model=AlertListResponse,
    summary="Get compliance alerts (HR admin only)"
)
async def get_compliance_alerts(
    resolved: Optional[bool] = Query(None, description="Filter by resolved status"),
    alert_type: Optional[str] = Query(None, description="Filter by alert type"),
    limit: int = Query(100, ge=1, le=1000),
    user_id: str = Depends(get_current_user_id),
    service: EnterpriseService = Depends(get_enterprise_service),
):
    """Get compliance alerts for organization. Requires hr_admin role."""
    employee = await require_role(user_id, ["hr_admin", "admin"], service)

    alerts = await service.get_compliance_alerts(
        employee.org_id,
        resolved=resolved,
        alert_type=alert_type,
        limit=limit
    )
    return AlertListResponse(alerts=alerts)


@router.post(
    "/compliance/alerts/{alert_id}/resolve",
    response_model=ComplianceAlertResponse,
    summary="Resolve compliance alert"
)
async def resolve_compliance_alert(
    alert_id: str,
    request: ResolveAlertRequest,
    user_id: str = Depends(get_current_user_id),
    service: EnterpriseService = Depends(get_enterprise_service),
):
    """Resolve a compliance alert. Requires hr_admin role."""
    employee = await require_role(user_id, ["hr_admin", "admin"], service)

    try:
        return await service.resolve_alert(
            alert_id=alert_id,
            resolved_by=employee.id,
            notes=request.resolution_notes
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# =============================================================================
# API Key Approval Endpoints (HR Admin)
# =============================================================================

@router.post(
    "/api-keys/{key_id}/approve",
    response_model=EmployeeAPIKeyResponse,
    summary="Approve API key (HR admin only)"
)
async def approve_api_key(
    key_id: str,
    request: EmployeeAPIKeyApproval,
    user_id: str = Depends(get_current_user_id),
    service: EnterpriseService = Depends(get_enterprise_service),
):
    """Approve or reject an API key. Requires hr_admin role."""
    employee = await require_role(user_id, ["hr_admin", "admin"], service)

    try:
        return await service.approve_api_key(
            key_id=key_id,
            approved_by=employee.id,
            notes=request.compliance_notes
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete(
    "/api-keys/{key_id}",
    response_model=EmployeeAPIKeyResponse,
    summary="Revoke API key (admin only)"
)
async def revoke_api_key(
    key_id: str,
    user_id: str = Depends(get_current_user_id),
    service: EnterpriseService = Depends(get_enterprise_service),
):
    """Revoke an API key. Requires admin role."""
    employee = await require_role(user_id, ["admin", "hr_admin"], service)

    try:
        return await service.revoke_api_key(
            key_id=key_id,
            revoked_by=employee.id,
            reason="Revoked by admin"
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# =============================================================================
# Provider Compliance Endpoints
# =============================================================================

@router.get(
    "/providers/chinese",
    response_model=ProviderListResponse,
    summary="List Chinese AI providers"
)
async def list_chinese_providers(
    user_id: str = Depends(get_current_user_id),
    service: EnterpriseService = Depends(get_enterprise_service),
):
    """List all Chinese AI providers for compliance awareness."""
    providers = await service.get_chinese_providers()
    return ProviderListResponse(providers=providers)


@router.get(
    "/providers/{provider_id}/blocked",
    response_model=ProviderBlockedResponse,
    summary="Check if provider is blocked"
)
async def check_provider_blocked(
    provider_id: str,
    user_id: str = Depends(get_current_user_id),
    service: EnterpriseService = Depends(get_enterprise_service),
):
    """Check if a provider is blocked by organization policy."""
    employee = await service.get_employee_by_auth_user(user_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    is_blocked = await service.is_provider_blocked(employee.org_id, provider_id)
    return ProviderBlockedResponse(provider=provider_id, is_blocked=is_blocked)
