# Plan: Enterprise Multi-Tenant Schema - TDD Implementation

## Overview

Build enterprise multi-tenant AI cost tracking with HR/Compliance focus using **Test-Driven Development (TDD)**. This enables tracking of 500-1000 employees across work/personal accounts with compliance flags for Chinese AI models.

**MVP User**: Tim (tim@coperniq.io + tkipper@gmail.com) tracking 9 providers
**Enterprise Target**: HR/Compliance teams tracking AI responsible deployment

---

## Phase 1: Database Migrations

### Files to Create

```
migrations/enterprise_001_organizations.sql
migrations/enterprise_002_departments_employees.sql
migrations/enterprise_003_api_keys_providers.sql
migrations/enterprise_004_usage_alerts.sql
migrations/enterprise_005_rls_policies.sql
```

### Key Tables

| Table               | Purpose                                        |
| ------------------- | ---------------------------------------------- |
| `organizations`     | Multi-tenant companies with AI policy settings |
| `departments`       | Org units with budgets and managers            |
| `employees`         | Users with work + personal email linking       |
| `employee_api_keys` | Encrypted API keys (work/personal)             |
| `ai_providers`      | Provider registry with compliance flags        |
| `ai_usage_log`      | Per-request usage tracking                     |
| `compliance_alerts` | Chinese model flags, budget alerts             |

### AI Providers Registry (Pre-seeded)

```sql
INSERT INTO ai_providers VALUES
('deepseek', 'DeepSeek', 'CN', 'high', '⚠️ Chinese company'),
('qwen', 'Alibaba Qwen', 'CN', 'high', '⚠️ Chinese company'),
('baidu', 'Baidu ERNIE', 'CN', 'high', '⚠️ Chinese company'),
('anthropic', 'Anthropic Claude', 'US', 'low', 'SOC2 certified'),
('openai', 'OpenAI', 'US', 'low', 'SOC2, GDPR compliant');
```

---

## Phase 2: Pydantic Models (TDD)

### Test First: `tests/test_enterprise_models.py`

```python
def test_account_type_enum():
    key = EmployeeAPIKeyCreate(provider="anthropic", account_type=AccountType.PERSONAL, ...)
    assert key.account_type == "personal"

def test_chinese_provider_flagged():
    provider = AIProviderInfo(id="deepseek", headquarters_country="CN", risk_level="high")
    assert provider.is_chinese_company
    assert provider.requires_compliance_review
```

### Models to Create: `app/models/enterprise.py`

- `AccountType` enum (work, personal, default)
- `EmployeeRole` enum (employee, manager, admin, hr_admin)
- `RiskLevel` enum (low, medium, high, blocked)
- `OrganizationCreate/Response`
- `EmployeeCreate/Response`
- `EmployeeAPIKeyCreate/Response`
- `AIProviderInfo`
- `ComplianceAlert`
- `UsageLogEntry`

---

## Phase 3: Service Layer (TDD)

### Test First: `tests/test_enterprise_service.py`

```python
async def test_add_api_key_encrypted():
    key = await service.add_employee_api_key(employee_id, "anthropic", "sk-ant-xxx", "work")
    assert key.api_key_encrypted != "sk-ant-xxx"  # Must be encrypted!

async def test_chinese_provider_triggers_alert():
    alerts = await service.log_usage(employee_id, provider="deepseek", cost=0.50)
    assert alerts[0].alert_type == "blocked_provider"
    assert "Chinese" in alerts[0].message
```

### Services to Create

| File                                 | Responsibility                     |
| ------------------------------------ | ---------------------------------- |
| `app/services/enterprise_service.py` | Organization, employee, usage CRUD |
| `app/services/encryption_service.py` | AES-256 encryption for API keys    |
| `app/services/compliance_service.py` | Alert generation, budget checks    |

### Key Methods

```python
class EnterpriseService:
    async def create_organization(name, domain, admin_email)
    async def add_employee(org_id, email, role, dept_id)
    async def add_employee_api_key(employee_id, provider, api_key, account_type)
    async def log_usage(employee_id, provider, model, cost_usd, tokens)
    async def get_compliance_alerts(org_id, filters)
    async def get_spend_by_department(org_id, period)
```

---

## Phase 4: API Routers (TDD)

### Test First: `tests/test_enterprise_endpoints.py`

```python
def test_create_org_auth_required(client):
    response = client.post("/api/enterprise/organizations", json={...})
    assert response.status_code == 401

def test_link_personal_account(client, auth_headers):
    response = client.post("/api/enterprise/employees/me/link-personal",
        json={"personal_email": "tkipper@gmail.com", "consent_given": True},
        headers=auth_headers)
    assert response.status_code == 200
```

### Endpoints to Create: `app/routers/enterprise.py`

| Endpoint                           | Role Required | Purpose             |
| ---------------------------------- | ------------- | ------------------- |
| `POST /organizations`              | admin         | Create organization |
| `POST /employees/me/api-keys`      | any           | Add my API key      |
| `GET /employees/me/usage`          | any           | My usage dashboard  |
| `POST /employees/me/link-personal` | any           | Link personal email |
| `GET /team/usage`                  | manager       | Department usage    |
| `GET /compliance/alerts`           | hr_admin      | Compliance alerts   |
| `GET /org/spend-by-department`     | hr_admin      | Spend breakdown     |

---

## Phase 5: Quality Gates

### Gate 1: Unit Tests (Before Each Commit)

```bash
pytest tests/test_enterprise_models.py tests/test_encryption_service.py -v
```

### Gate 2: Integration Tests (Before PR)

```bash
pytest tests/test_enterprise_service.py tests/test_enterprise_endpoints.py -v
pytest --cov=app/services/enterprise --cov-fail-under=80
```

### Gate 3: Security Audit Checklist

- [ ] API keys encrypted at rest (AES-256)
- [ ] Personal email consent tracked (GDPR)
- [ ] RLS policies verified (multi-tenant isolation)
- [ ] No secrets in logs or error responses
- [ ] Rate limiting on key addition

### Gate 4: Compliance Verification

- [ ] DeepSeek, Qwen, Baidu trigger `blocked_provider` alerts
- [ ] Budget 80% threshold triggers `warning` alert
- [ ] Chinese data residency flagged correctly

---

## Implementation Order (TDD Cycle)

### Step 1: Migrations (Day 1)

1. Create 5 migration SQL files
2. Run in Supabase SQL Editor (in order)
3. Verify tables created with `\dt` in SQL Editor

### Step 2: Models + Tests (Day 2)

1. Write `tests/test_enterprise_models.py` (RED)
2. Implement `app/models/enterprise.py` (GREEN)
3. Refactor for clarity

### Step 3: Encryption Service (Day 3)

1. Write `tests/test_encryption_service.py` (RED)
2. Implement `app/services/encryption_service.py` (GREEN)
3. Use cryptography library for AES-256-GCM

### Step 4: Enterprise Service (Day 4-5)

1. Write `tests/test_enterprise_service.py` (RED)
2. Implement `app/services/enterprise_service.py` (GREEN)
3. Integrate encryption service

### Step 5: API Endpoints (Day 6)

1. Write `tests/test_enterprise_endpoints.py` (RED)
2. Implement `app/routers/enterprise.py` (GREEN)
3. Register router in `app/main.py`

### Step 6: Integration & Docs (Day 7)

1. Full integration test suite
2. Update `docs/ENTERPRISE_SCHEMA.md`
3. Create Postman collection

---

## Critical Files to Create/Modify

### New Files (13 total)

```
migrations/enterprise_001_organizations.sql
migrations/enterprise_002_departments_employees.sql
migrations/enterprise_003_api_keys_providers.sql
migrations/enterprise_004_usage_alerts.sql
migrations/enterprise_005_rls_policies.sql
app/models/enterprise.py
app/services/enterprise_service.py
app/services/encryption_service.py
app/services/compliance_service.py
app/routers/enterprise.py
tests/test_enterprise_models.py
tests/test_enterprise_service.py
tests/test_enterprise_endpoints.py
```

### Files to Modify

```
app/main.py              # Add enterprise router
tests/conftest.py        # Add enterprise fixtures
requirements.txt         # Add cryptography library
docs/ENTERPRISE_SCHEMA.md  # Update with implementation
```

---

## Success Criteria

1. **Tim MVP**: Track tim@coperniq.io + tkipper@gmail.com across 9 providers
2. **Compliance**: DeepSeek/Qwen/Baidu usage triggers automatic alerts
3. **Security**: All API keys encrypted with AES-256, never logged
4. **Multi-Tenancy**: RLS policies isolate org data completely
5. **Scalability**: Schema supports 500-1000 employees
6. **Test Coverage**: 80%+ on all enterprise code
7. **HR Dashboard**: Spend by department, compliance alerts visible

---

## Dependencies to Add

```
# requirements.txt additions
cryptography>=41.0.0    # AES-256 encryption
```

---

## Notes

- Schema based on `docs/ENTERPRISE_SCHEMA.md` (326 lines)
- Follows existing patterns from `app/models/api_keys.py`
- Uses Supabase RLS for multi-tenant isolation
- Existing auth in `app/auth.py` provides JWT validation
- Test patterns from `tests/conftest.py` (auth fixtures)
