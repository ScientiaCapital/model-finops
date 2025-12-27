-- Enterprise Schema Migration 003: API Keys & AI Providers Registry
-- Encrypted key storage and compliance metadata
-- Run AFTER: enterprise_002_departments_employees.sql

-- =============================================================================
-- AI PROVIDERS REGISTRY (Compliance Metadata)
-- =============================================================================

CREATE TABLE IF NOT EXISTS ai_providers (
    id TEXT PRIMARY KEY,                         -- "deepseek", "anthropic", etc.
    display_name TEXT NOT NULL,

    -- Compliance info
    headquarters_country TEXT,                   -- "US", "CN", "UK", "FR"
    data_residency TEXT[],                       -- ARRAY['us', 'eu', 'cn']
    soc2_certified BOOLEAN DEFAULT FALSE,
    hipaa_compliant BOOLEAN DEFAULT FALSE,
    gdpr_compliant BOOLEAN DEFAULT FALSE,

    -- Risk assessment
    risk_level TEXT DEFAULT 'medium',            -- "low", "medium", "high", "blocked"
    risk_notes TEXT,                             -- "Data may be stored in China"

    -- Pricing reference
    pricing_url TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed with known providers (compliance data)
INSERT INTO ai_providers (id, display_name, headquarters_country, data_residency, soc2_certified, hipaa_compliant, gdpr_compliant, risk_level, risk_notes) VALUES
    ('anthropic', 'Anthropic Claude', 'US', ARRAY['us'], TRUE, FALSE, TRUE, 'low', 'SOC2 certified, US data centers'),
    ('openai', 'OpenAI', 'US', ARRAY['us', 'eu'], TRUE, FALSE, TRUE, 'low', 'SOC2, GDPR compliant'),
    ('azure-openai', 'Azure OpenAI', 'US', ARRAY['us', 'eu', 'asia'], TRUE, TRUE, TRUE, 'low', 'Enterprise compliance, HIPAA available'),
    ('google', 'Google Gemini', 'US', ARRAY['us', 'eu'], TRUE, FALSE, TRUE, 'low', 'Enterprise tier available'),
    ('openrouter', 'OpenRouter', 'US', ARRAY['us'], FALSE, FALSE, FALSE, 'medium', 'Routes to various providers'),
    ('cerebras', 'Cerebras', 'US', ARRAY['us'], FALSE, FALSE, FALSE, 'medium', 'Fast inference, US-based'),
    ('groq', 'Groq', 'US', ARRAY['us'], FALSE, FALSE, FALSE, 'low', 'US-based inference'),
    ('mistral', 'Mistral AI', 'FR', ARRAY['eu'], FALSE, FALSE, TRUE, 'low', 'EU-based, GDPR native'),
    ('deepseek', 'DeepSeek', 'CN', ARRAY['cn'], FALSE, FALSE, FALSE, 'high', 'Chinese company, data stored in China'),
    ('qwen', 'Alibaba Qwen', 'CN', ARRAY['cn'], FALSE, FALSE, FALSE, 'high', 'Chinese company (Alibaba Cloud)'),
    ('baidu', 'Baidu ERNIE', 'CN', ARRAY['cn'], FALSE, FALSE, FALSE, 'high', 'Chinese company'),
    ('elevenlabs', 'ElevenLabs', 'US', ARRAY['us', 'eu'], TRUE, FALSE, TRUE, 'low', 'Voice AI, SOC2 certified'),
    ('deepgram', 'Deepgram', 'US', ARRAY['us'], TRUE, FALSE, FALSE, 'low', 'Speech-to-text, enterprise ready'),
    ('cartesia', 'Cartesia', 'US', ARRAY['us'], FALSE, FALSE, FALSE, 'low', 'Voice AI, US-based'),
    ('assemblyai', 'AssemblyAI', 'US', ARRAY['us'], TRUE, FALSE, TRUE, 'low', 'Speech AI, SOC2 certified')
ON CONFLICT (id) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    headquarters_country = EXCLUDED.headquarters_country,
    data_residency = EXCLUDED.data_residency,
    soc2_certified = EXCLUDED.soc2_certified,
    hipaa_compliant = EXCLUDED.hipaa_compliant,
    gdpr_compliant = EXCLUDED.gdpr_compliant,
    risk_level = EXCLUDED.risk_level,
    risk_notes = EXCLUDED.risk_notes,
    updated_at = NOW();

-- =============================================================================
-- EMPLOYEE API KEYS (Encrypted Storage)
-- =============================================================================

CREATE TABLE IF NOT EXISTS employee_api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,

    -- Provider info
    provider TEXT NOT NULL REFERENCES ai_providers(id),
    account_type TEXT NOT NULL,                  -- "work" or "personal"

    -- Encrypted key storage (AES-256-GCM)
    api_key_encrypted TEXT NOT NULL,             -- Encrypted with app-level key
    key_last_four TEXT,                          -- "...3ABC" for display only
    encryption_version INTEGER DEFAULT 1,        -- For key rotation

    -- Compliance flags
    is_approved BOOLEAN DEFAULT FALSE,           -- HR approved?
    approved_by UUID REFERENCES employees(id),
    approved_at TIMESTAMPTZ,
    data_residency TEXT,                         -- Override if known: "us", "eu", "cn"
    compliance_notes TEXT,

    -- Usage tracking (aggregated)
    last_used_at TIMESTAMPTZ,
    total_requests INTEGER DEFAULT 0,
    total_spend_usd DECIMAL(10,2) DEFAULT 0,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    revoked_at TIMESTAMPTZ,
    revoked_by UUID REFERENCES employees(id),
    revoke_reason TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_account_type CHECK (account_type IN ('work', 'personal')),
    UNIQUE(employee_id, provider, account_type)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_employee_api_keys_employee_id ON employee_api_keys(employee_id);
CREATE INDEX IF NOT EXISTS idx_employee_api_keys_provider ON employee_api_keys(provider);
CREATE INDEX IF NOT EXISTS idx_employee_api_keys_account_type ON employee_api_keys(account_type);
CREATE INDEX IF NOT EXISTS idx_employee_api_keys_is_active ON employee_api_keys(is_active) WHERE is_active = TRUE;

-- Enable RLS
ALTER TABLE employee_api_keys ENABLE ROW LEVEL SECURITY;

-- Trigger
CREATE TRIGGER update_employee_api_keys_updated_at
    BEFORE UPDATE ON employee_api_keys
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- HELPER FUNCTIONS
-- =============================================================================

-- Check if provider is from China (for compliance alerts)
CREATE OR REPLACE FUNCTION is_chinese_provider(provider_id TEXT)
RETURNS BOOLEAN AS $$
    SELECT headquarters_country = 'CN'
    FROM ai_providers
    WHERE id = provider_id;
$$ LANGUAGE sql STABLE;

-- Get provider risk level
CREATE OR REPLACE FUNCTION get_provider_risk_level(provider_id TEXT)
RETURNS TEXT AS $$
    SELECT COALESCE(risk_level, 'unknown')
    FROM ai_providers
    WHERE id = provider_id;
$$ LANGUAGE sql STABLE;

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE ai_providers IS 'Registry of AI providers with compliance metadata';
COMMENT ON TABLE employee_api_keys IS 'Encrypted API keys for work/personal accounts';
COMMENT ON COLUMN employee_api_keys.api_key_encrypted IS 'AES-256-GCM encrypted, never log or expose';
COMMENT ON COLUMN employee_api_keys.account_type IS 'work = company account, personal = employee personal account';
