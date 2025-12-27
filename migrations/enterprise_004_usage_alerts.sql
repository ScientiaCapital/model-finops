-- Enterprise Schema Migration 004: Usage Logging & Compliance Alerts
-- Per-request tracking and automatic compliance flagging
-- Run AFTER: enterprise_003_api_keys_providers.sql

-- =============================================================================
-- AI USAGE LOG (Per-Request Tracking)
-- =============================================================================

CREATE TABLE IF NOT EXISTS ai_usage_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    api_key_id UUID REFERENCES employee_api_keys(id) ON DELETE SET NULL,

    -- Request details
    provider TEXT NOT NULL REFERENCES ai_providers(id),
    model TEXT,                                  -- "gpt-4", "claude-3-opus", "deepseek-chat"

    -- Usage metrics
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER GENERATED ALWAYS AS (input_tokens + output_tokens) STORED,
    cost_usd DECIMAL(10,6) DEFAULT 0,
    latency_ms INTEGER,

    -- Context
    account_type TEXT,                           -- "work" or "personal"
    endpoint TEXT,                               -- API endpoint used
    request_metadata JSONB DEFAULT '{}',         -- Additional context

    -- Compliance
    flagged_for_review BOOLEAN DEFAULT FALSE,
    flag_reason TEXT,
    reviewed_by UUID REFERENCES employees(id),
    reviewed_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for analytics queries
CREATE INDEX IF NOT EXISTS idx_usage_log_employee_id ON ai_usage_log(employee_id);
CREATE INDEX IF NOT EXISTS idx_usage_log_provider ON ai_usage_log(provider);
CREATE INDEX IF NOT EXISTS idx_usage_log_created_at ON ai_usage_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_usage_log_account_type ON ai_usage_log(account_type);
CREATE INDEX IF NOT EXISTS idx_usage_log_flagged ON ai_usage_log(flagged_for_review) WHERE flagged_for_review = TRUE;

-- Composite index for department spend queries
CREATE INDEX IF NOT EXISTS idx_usage_log_employee_date ON ai_usage_log(employee_id, created_at DESC);

-- Enable RLS
ALTER TABLE ai_usage_log ENABLE ROW LEVEL SECURITY;

-- =============================================================================
-- COMPLIANCE ALERTS
-- =============================================================================

CREATE TABLE IF NOT EXISTS compliance_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    employee_id UUID REFERENCES employees(id) ON DELETE SET NULL,
    dept_id UUID REFERENCES departments(id) ON DELETE SET NULL,

    -- Alert details
    alert_type TEXT NOT NULL,                    -- See types below
    severity TEXT NOT NULL DEFAULT 'warning',    -- "info", "warning", "critical"
    provider TEXT REFERENCES ai_providers(id),
    model TEXT,

    -- Content
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    details JSONB DEFAULT '{}',                  -- Additional context

    -- Resolution
    resolved BOOLEAN DEFAULT FALSE,
    resolved_by UUID REFERENCES employees(id),
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT,

    -- Auto-dismiss settings
    auto_dismiss_at TIMESTAMPTZ,                 -- Auto-resolve after this time
    snooze_until TIMESTAMPTZ,                    -- Hide until this time

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Alert Types:
-- "blocked_provider"    - Employee used a blocked provider (e.g., DeepSeek)
-- "chinese_provider"    - Employee used a Chinese AI provider
-- "unapproved_model"    - New model detected, needs approval
-- "budget_warning"      - Department at X% of budget
-- "budget_exceeded"     - Department exceeded budget
-- "personal_high_usage" - High personal account usage
-- "data_residency"      - Data sent to restricted region
-- "new_api_key"         - New API key added, needs approval

-- Indexes
CREATE INDEX IF NOT EXISTS idx_compliance_alerts_org_id ON compliance_alerts(org_id);
CREATE INDEX IF NOT EXISTS idx_compliance_alerts_employee_id ON compliance_alerts(employee_id);
CREATE INDEX IF NOT EXISTS idx_compliance_alerts_resolved ON compliance_alerts(resolved);
CREATE INDEX IF NOT EXISTS idx_compliance_alerts_severity ON compliance_alerts(severity);
CREATE INDEX IF NOT EXISTS idx_compliance_alerts_created_at ON compliance_alerts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_compliance_alerts_type ON compliance_alerts(alert_type);

-- Enable RLS
ALTER TABLE compliance_alerts ENABLE ROW LEVEL SECURITY;

-- =============================================================================
-- AUTOMATIC ALERT GENERATION (Triggers)
-- =============================================================================

-- Trigger: Auto-flag Chinese provider usage
CREATE OR REPLACE FUNCTION trigger_chinese_provider_alert()
RETURNS TRIGGER AS $$
DECLARE
    emp_org_id UUID;
    emp_name TEXT;
BEGIN
    -- Check if provider is Chinese
    IF is_chinese_provider(NEW.provider) THEN
        -- Get employee's org
        SELECT org_id, name INTO emp_org_id, emp_name
        FROM employees WHERE id = NEW.employee_id;

        -- Create compliance alert
        INSERT INTO compliance_alerts (
            org_id, employee_id, alert_type, severity, provider, model,
            title, message, details
        ) VALUES (
            emp_org_id,
            NEW.employee_id,
            'chinese_provider',
            'critical',
            NEW.provider,
            NEW.model,
            'Chinese AI Provider Usage Detected',
            format('Employee %s used %s (%s). Data may be stored in China.',
                   COALESCE(emp_name, 'Unknown'),
                   NEW.provider,
                   COALESCE(NEW.model, 'unknown model')),
            jsonb_build_object(
                'usage_id', NEW.id,
                'cost_usd', NEW.cost_usd,
                'tokens', NEW.total_tokens,
                'account_type', NEW.account_type
            )
        );

        -- Also flag the usage record
        NEW.flagged_for_review := TRUE;
        NEW.flag_reason := 'Chinese provider: data residency concern';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER check_chinese_provider
    BEFORE INSERT ON ai_usage_log
    FOR EACH ROW
    EXECUTE FUNCTION trigger_chinese_provider_alert();

-- =============================================================================
-- ANALYTICS FUNCTIONS
-- =============================================================================

-- Get department spend for current month
CREATE OR REPLACE FUNCTION get_department_spend(dept_id UUID, period_start TIMESTAMPTZ DEFAULT DATE_TRUNC('month', NOW()))
RETURNS TABLE (
    total_spend DECIMAL,
    total_requests BIGINT,
    employee_count BIGINT,
    top_provider TEXT,
    budget_percent DECIMAL
) AS $$
    SELECT
        COALESCE(SUM(u.cost_usd), 0) as total_spend,
        COUNT(u.id) as total_requests,
        COUNT(DISTINCT u.employee_id) as employee_count,
        MODE() WITHIN GROUP (ORDER BY u.provider) as top_provider,
        CASE
            WHEN d.budget_usd > 0 THEN ROUND(SUM(u.cost_usd) / d.budget_usd * 100, 1)
            ELSE 0
        END as budget_percent
    FROM departments d
    LEFT JOIN employees e ON e.dept_id = d.id
    LEFT JOIN ai_usage_log u ON u.employee_id = e.id AND u.created_at >= period_start
    WHERE d.id = dept_id
    GROUP BY d.id, d.budget_usd;
$$ LANGUAGE sql STABLE;

-- Get org-wide compliance summary
CREATE OR REPLACE FUNCTION get_compliance_summary(organization_id UUID)
RETURNS TABLE (
    total_alerts BIGINT,
    critical_unresolved BIGINT,
    chinese_usage_count BIGINT,
    budget_warnings BIGINT
) AS $$
    SELECT
        COUNT(*) as total_alerts,
        COUNT(*) FILTER (WHERE severity = 'critical' AND NOT resolved) as critical_unresolved,
        COUNT(*) FILTER (WHERE alert_type = 'chinese_provider') as chinese_usage_count,
        COUNT(*) FILTER (WHERE alert_type IN ('budget_warning', 'budget_exceeded')) as budget_warnings
    FROM compliance_alerts
    WHERE org_id = organization_id
    AND created_at >= DATE_TRUNC('month', NOW());
$$ LANGUAGE sql STABLE;

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE ai_usage_log IS 'Per-request AI usage tracking for cost and compliance';
COMMENT ON TABLE compliance_alerts IS 'Automated compliance alerts for HR/Admin review';
COMMENT ON COLUMN ai_usage_log.flagged_for_review IS 'Set by triggers when compliance issue detected';
COMMENT ON COLUMN compliance_alerts.alert_type IS 'Types: blocked_provider, chinese_provider, budget_warning, etc.';
