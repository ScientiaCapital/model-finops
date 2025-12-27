# Enterprise Multi-Tenant Schema for AI Cost & Compliance

## Use Case: HR/Compliance AI Governance

**Target Users:**
- HR Leaders managing AI policy
- Compliance teams tracking data residency
- Finance tracking AI spend by department
- Employees linking work + personal AI accounts

---

## Database Schema

### Organizations (Companies)
```sql
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,                    -- "Coperniq"
    domain TEXT UNIQUE,                    -- "coperniq.io"
    plan TEXT DEFAULT 'starter',           -- starter, growth, enterprise
    settings JSONB DEFAULT '{}',           -- AI policy settings
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- AI Policy Settings Example:
-- {
--   "blocked_providers": ["deepseek", "qwen", "baidu"],
--   "require_approval": ["openai", "anthropic"],
--   "auto_approved": ["azure-openai"],  -- US data residency
--   "max_monthly_budget_usd": 10000,
--   "alert_threshold_percent": 80
-- }
```

### Departments/Teams
```sql
CREATE TABLE departments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),
    name TEXT NOT NULL,                    -- "Engineering", "Sales", "Marketing"
    budget_usd DECIMAL(10,2),              -- Monthly AI budget
    manager_id UUID,                       -- References employees
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Employees (Users)
```sql
CREATE TABLE employees (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),
    dept_id UUID REFERENCES departments(id),

    -- Identity
    email TEXT NOT NULL,                   -- tim@coperniq.io (work)
    name TEXT,
    role TEXT DEFAULT 'employee',          -- employee, manager, admin, hr_admin

    -- Personal account linking (optional)
    personal_email TEXT,                   -- tkipper@gmail.com
    personal_linked_at TIMESTAMPTZ,
    personal_consent BOOLEAN DEFAULT FALSE, -- GDPR consent

    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, email)
);
```

### API Keys (Work + Personal)
```sql
CREATE TABLE employee_api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID REFERENCES employees(id),

    -- Provider info
    provider TEXT NOT NULL,                -- "anthropic", "deepseek", "elevenlabs"
    account_type TEXT NOT NULL,            -- "work" or "personal"

    -- Encrypted key storage
    api_key_encrypted TEXT NOT NULL,       -- AES-256 encrypted
    key_last_four TEXT,                    -- "...3ABC" for display

    -- Compliance flags
    is_approved BOOLEAN DEFAULT FALSE,     -- HR approved?
    data_residency TEXT,                   -- "us", "eu", "cn", "unknown"
    compliance_notes TEXT,

    -- Usage tracking
    last_used_at TIMESTAMPTZ,
    total_spend_usd DECIMAL(10,2) DEFAULT 0,

    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### AI Providers Registry (Compliance Data)
```sql
CREATE TABLE ai_providers (
    id TEXT PRIMARY KEY,                   -- "deepseek", "anthropic", etc.
    display_name TEXT NOT NULL,

    -- Compliance info
    headquarters_country TEXT,             -- "US", "CN", "UK"
    data_residency TEXT[],                 -- ["us", "eu"]
    soc2_certified BOOLEAN DEFAULT FALSE,
    hipaa_compliant BOOLEAN DEFAULT FALSE,
    gdpr_compliant BOOLEAN DEFAULT FALSE,

    -- Risk level for HR
    risk_level TEXT,                       -- "low", "medium", "high", "blocked"
    risk_notes TEXT,                       -- "Data may be stored in China"

    -- Pricing for cost tracking
    pricing_url TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Pre-populate with providers
INSERT INTO ai_providers (id, display_name, headquarters_country, data_residency, risk_level, risk_notes) VALUES
('anthropic', 'Anthropic Claude', 'US', ARRAY['us'], 'low', 'SOC2, US data centers'),
('openai', 'OpenAI', 'US', ARRAY['us', 'eu'], 'low', 'SOC2, GDPR compliant'),
('azure-openai', 'Azure OpenAI', 'US', ARRAY['us', 'eu', 'asia'], 'low', 'Enterprise compliance'),
('google', 'Google Gemini', 'US', ARRAY['us', 'eu'], 'low', 'Enterprise tier available'),
('deepseek', 'DeepSeek', 'CN', ARRAY['cn'], 'high', '⚠️ Chinese company, data stored in China'),
('qwen', 'Alibaba Qwen', 'CN', ARRAY['cn'], 'high', '⚠️ Chinese company, Alibaba Cloud'),
('baidu', 'Baidu ERNIE', 'CN', ARRAY['cn'], 'high', '⚠️ Chinese company'),
('mistral', 'Mistral AI', 'FR', ARRAY['eu'], 'low', 'EU-based, GDPR native'),
('groq', 'Groq', 'US', ARRAY['us'], 'low', 'US-based inference'),
('elevenlabs', 'ElevenLabs', 'US', ARRAY['us', 'eu'], 'low', 'Voice AI, SOC2'),
('deepgram', 'Deepgram', 'US', ARRAY['us'], 'low', 'Speech-to-text, enterprise ready');
```

### Usage Tracking (Per Request)
```sql
CREATE TABLE ai_usage_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID REFERENCES employees(id),
    api_key_id UUID REFERENCES employee_api_keys(id),

    -- Request details
    provider TEXT NOT NULL,
    model TEXT,                            -- "gpt-4", "claude-3-opus", "deepseek-chat"

    -- Usage metrics
    input_tokens INT,
    output_tokens INT,
    cost_usd DECIMAL(10,6),

    -- Compliance tracking
    account_type TEXT,                     -- "work" or "personal"
    flagged_for_review BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast queries
CREATE INDEX idx_usage_employee ON ai_usage_log(employee_id, created_at DESC);
CREATE INDEX idx_usage_provider ON ai_usage_log(provider, created_at DESC);
```

### Compliance Alerts
```sql
CREATE TABLE compliance_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),
    employee_id UUID REFERENCES employees(id),

    -- Alert details
    alert_type TEXT NOT NULL,              -- "blocked_provider", "budget_exceeded", "unapproved_model"
    severity TEXT NOT NULL,                -- "info", "warning", "critical"
    provider TEXT,

    message TEXT NOT NULL,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_by UUID,
    resolved_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Example alerts:
-- "Employee Tim used DeepSeek (Chinese AI) - requires HR review"
-- "Engineering department at 85% of monthly AI budget"
-- "New unapproved model detected: qwen-72b"
```

---

## HR Admin Dashboard Views

### 1. Company-Wide AI Spend
```sql
-- Monthly spend by department
SELECT
    d.name as department,
    COUNT(DISTINCT e.id) as employees_using_ai,
    SUM(u.cost_usd) as total_spend,
    d.budget_usd as budget,
    ROUND(SUM(u.cost_usd) / d.budget_usd * 100, 1) as percent_used
FROM departments d
JOIN employees e ON e.dept_id = d.id
JOIN ai_usage_log u ON u.employee_id = e.id
WHERE u.created_at >= DATE_TRUNC('month', NOW())
GROUP BY d.id
ORDER BY total_spend DESC;
```

### 2. Chinese Model Usage (Compliance Alert)
```sql
-- Flag any usage of Chinese AI providers
SELECT
    e.name,
    e.email,
    d.name as department,
    u.provider,
    u.model,
    SUM(u.cost_usd) as spend,
    COUNT(*) as request_count
FROM ai_usage_log u
JOIN employees e ON e.id = u.employee_id
JOIN departments d ON d.id = e.dept_id
JOIN ai_providers p ON p.id = u.provider
WHERE p.headquarters_country = 'CN'
  AND u.created_at >= NOW() - INTERVAL '30 days'
GROUP BY e.id, d.id, u.provider, u.model
ORDER BY request_count DESC;
```

### 3. Personal vs Work Spend (Expense Reporting)
```sql
-- Employees expensing personal AI usage
SELECT
    e.name,
    e.email,
    e.personal_email,
    SUM(CASE WHEN u.account_type = 'work' THEN u.cost_usd ELSE 0 END) as work_spend,
    SUM(CASE WHEN u.account_type = 'personal' THEN u.cost_usd ELSE 0 END) as personal_spend,
    SUM(u.cost_usd) as total_expensable
FROM employees e
JOIN ai_usage_log u ON u.employee_id = e.id
WHERE u.created_at >= DATE_TRUNC('month', NOW())
GROUP BY e.id
HAVING SUM(CASE WHEN u.account_type = 'personal' THEN 1 ELSE 0 END) > 0
ORDER BY personal_spend DESC;
```

---

## Row-Level Security (RLS)

```sql
-- Employees see only their own data
CREATE POLICY employee_own_data ON ai_usage_log
    FOR SELECT USING (employee_id = auth.uid());

-- Managers see their department
CREATE POLICY manager_dept_data ON ai_usage_log
    FOR SELECT USING (
        employee_id IN (
            SELECT id FROM employees
            WHERE dept_id = (SELECT dept_id FROM employees WHERE id = auth.uid())
        )
    );

-- HR Admins see entire org
CREATE POLICY hr_admin_org_data ON ai_usage_log
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM employees
            WHERE id = auth.uid()
            AND role = 'hr_admin'
        )
    );
```

---

## API Endpoints for Enterprise

```
# Employee self-service
POST /api/keys              - Link new API key (work or personal)
GET  /api/usage/me          - My usage dashboard
GET  /api/spend/me          - My monthly spend

# Manager view
GET  /api/team/usage        - Department usage
GET  /api/team/spend        - Department spend vs budget

# HR Admin / Compliance
GET  /api/org/usage         - Company-wide usage
GET  /api/org/compliance    - Compliance alerts (Chinese models, etc.)
GET  /api/org/spend         - Spend by department
POST /api/org/policy        - Update AI policy (blocked providers, etc.)
GET  /api/org/employees     - Employee AI usage summary
```

---

## Your Wife's HR Compliance Pitch

**"AI Responsible Deployment Audit"**

1. **Discovery**: What AI tools are employees actually using?
2. **Risk Assessment**: Any Chinese models? Data residency issues?
3. **Policy Creation**: Approved vs blocked providers
4. **Ongoing Monitoring**: Real-time compliance alerts
5. **Expense Management**: Work vs personal AI spend

**Value Prop**: "Know exactly where your company's data is going and how much you're spending on AI - before it becomes a compliance nightmare."

---

## MVP for You (Tim)

Start with:
1. ✅ Your work APIs (tim@coperniq.io)
2. ✅ Your personal APIs (tkipper@gmail.com)
3. ✅ Track both in one dashboard
4. 🔜 Add compliance flags for each provider
5. 🔜 Export for expense reporting

You become the case study for both personal AND enterprise use.
