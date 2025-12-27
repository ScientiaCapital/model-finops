-- Enterprise Schema Migration 001: Organizations
-- Multi-tenant companies with AI policy settings
-- Run in Supabase SQL Editor: https://supabase.com/dashboard/project/YOUR_PROJECT/sql

-- =============================================================================
-- ORGANIZATIONS TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    domain TEXT UNIQUE,                          -- "coperniq.io" for SSO matching
    plan TEXT DEFAULT 'starter',                 -- starter, growth, enterprise
    settings JSONB DEFAULT '{}',                 -- AI policy settings (see below)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- AI Policy Settings Schema (stored in settings JSONB):
-- {
--   "blocked_providers": ["deepseek", "qwen", "baidu"],
--   "require_approval": ["openai", "anthropic"],
--   "auto_approved": ["azure-openai"],
--   "max_monthly_budget_usd": 10000,
--   "alert_threshold_percent": 80,
--   "data_residency_required": ["us", "eu"],
--   "require_soc2": true,
--   "allow_personal_accounts": true
-- }

-- Index for domain lookup (SSO matching)
CREATE INDEX IF NOT EXISTS idx_organizations_domain ON organizations(domain);

-- Enable RLS
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_organizations_updated_at
    BEFORE UPDATE ON organizations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE organizations IS 'Multi-tenant companies using AI Cost Optimizer';
COMMENT ON COLUMN organizations.domain IS 'Company domain for SSO matching (e.g., coperniq.io)';
COMMENT ON COLUMN organizations.plan IS 'Subscription plan: starter, growth, enterprise';
COMMENT ON COLUMN organizations.settings IS 'AI policy settings JSON (blocked providers, budgets, etc.)';
