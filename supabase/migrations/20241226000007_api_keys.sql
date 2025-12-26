-- ============================================================================
-- API KEY MANAGEMENT SYSTEM - Supabase Migration
-- ============================================================================
-- Purpose: Secure API key storage with rate limiting and usage tracking
--
-- Security Model:
-- - Keys stored as SHA-256 hashes (never plaintext)
-- - Per-key rate limits (requests per minute/day)
-- - Multi-tenant isolation via RLS policies
-- - Usage analytics for billing integration
-- ============================================================================

-- ============================================================================
-- TABLE: api_keys - Stores hashed API keys with metadata
-- ============================================================================

CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    key_prefix TEXT NOT NULL,           -- First 8 chars of key (sk-xxxxxxxx) for display
    key_hash TEXT NOT NULL UNIQUE,      -- SHA-256 hash of full key

    -- Permissions and limits
    permissions JSONB DEFAULT '["read", "write"]'::jsonb,
    rate_limit_per_minute INTEGER DEFAULT 60,
    rate_limit_per_day INTEGER DEFAULT 10000,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    last_used_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    revoked_reason TEXT,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,             -- Optional expiration

    -- Constraints
    CONSTRAINT api_keys_name_length CHECK (char_length(name) >= 1 AND char_length(name) <= 100),
    CONSTRAINT api_keys_prefix_format CHECK (key_prefix ~ '^sk-[a-zA-Z0-9]{4}$')
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_is_active ON api_keys(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_api_keys_last_used ON api_keys(last_used_at DESC);

-- ============================================================================
-- TABLE: api_key_usage - Detailed request logging per key
-- ============================================================================

CREATE TABLE IF NOT EXISTS api_key_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    api_key_id UUID NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,

    -- Request details
    endpoint TEXT NOT NULL,
    method TEXT NOT NULL,
    status_code INTEGER NOT NULL,

    -- Resource consumption
    tokens_in INTEGER DEFAULT 0,
    tokens_out INTEGER DEFAULT 0,
    cost_usd FLOAT DEFAULT 0,
    latency_ms FLOAT,

    -- Metadata
    ip_address INET,
    user_agent TEXT,
    request_id TEXT,

    -- Timing
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for analytics and rate limiting
CREATE INDEX IF NOT EXISTS idx_api_key_usage_key_id ON api_key_usage(api_key_id);
CREATE INDEX IF NOT EXISTS idx_api_key_usage_user_id ON api_key_usage(user_id);
CREATE INDEX IF NOT EXISTS idx_api_key_usage_created_at ON api_key_usage(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_api_key_usage_endpoint ON api_key_usage(endpoint);

-- Composite index for rate limit checking (key + time range)
CREATE INDEX IF NOT EXISTS idx_api_key_usage_rate_limit
    ON api_key_usage(api_key_id, created_at DESC);

-- ============================================================================
-- FUNCTION: validate_api_key - Validates key hash and returns user context
-- ============================================================================

CREATE OR REPLACE FUNCTION validate_api_key(p_key_hash TEXT)
RETURNS TABLE (
    key_id UUID,
    user_id TEXT,
    permissions JSONB,
    rate_limit_per_minute INTEGER,
    rate_limit_per_day INTEGER,
    is_valid BOOLEAN,
    error_message TEXT
) AS $$
DECLARE
    v_key RECORD;
BEGIN
    -- Find active key by hash
    SELECT * INTO v_key
    FROM api_keys k
    WHERE k.key_hash = p_key_hash
    LIMIT 1;

    -- Key not found
    IF v_key IS NULL THEN
        RETURN QUERY SELECT
            NULL::UUID,
            NULL::TEXT,
            NULL::JSONB,
            NULL::INTEGER,
            NULL::INTEGER,
            FALSE,
            'Invalid API key'::TEXT;
        RETURN;
    END IF;

    -- Key is revoked
    IF v_key.revoked_at IS NOT NULL OR v_key.is_active = FALSE THEN
        RETURN QUERY SELECT
            v_key.id,
            v_key.user_id,
            v_key.permissions,
            v_key.rate_limit_per_minute,
            v_key.rate_limit_per_day,
            FALSE,
            'API key has been revoked'::TEXT;
        RETURN;
    END IF;

    -- Key is expired
    IF v_key.expires_at IS NOT NULL AND v_key.expires_at < NOW() THEN
        RETURN QUERY SELECT
            v_key.id,
            v_key.user_id,
            v_key.permissions,
            v_key.rate_limit_per_minute,
            v_key.rate_limit_per_day,
            FALSE,
            'API key has expired'::TEXT;
        RETURN;
    END IF;

    -- Update last used timestamp
    UPDATE api_keys SET last_used_at = NOW() WHERE id = v_key.id;

    -- Return valid key info
    RETURN QUERY SELECT
        v_key.id,
        v_key.user_id,
        v_key.permissions,
        v_key.rate_limit_per_minute,
        v_key.rate_limit_per_day,
        TRUE,
        NULL::TEXT;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- FUNCTION: check_rate_limit - Enforces per-minute and per-day limits
-- ============================================================================

CREATE OR REPLACE FUNCTION check_rate_limit(p_api_key_id UUID)
RETURNS TABLE (
    is_allowed BOOLEAN,
    requests_this_minute INTEGER,
    requests_today INTEGER,
    minute_limit INTEGER,
    day_limit INTEGER,
    retry_after_seconds INTEGER
) AS $$
DECLARE
    v_key RECORD;
    v_minute_count INTEGER;
    v_day_count INTEGER;
BEGIN
    -- Get key limits
    SELECT rate_limit_per_minute, rate_limit_per_day INTO v_key
    FROM api_keys
    WHERE id = p_api_key_id AND is_active = TRUE;

    IF v_key IS NULL THEN
        RETURN QUERY SELECT FALSE, 0, 0, 0, 0, 0;
        RETURN;
    END IF;

    -- Count requests in last minute
    SELECT COUNT(*) INTO v_minute_count
    FROM api_key_usage
    WHERE api_key_id = p_api_key_id
      AND created_at > NOW() - INTERVAL '1 minute';

    -- Count requests today (UTC)
    SELECT COUNT(*) INTO v_day_count
    FROM api_key_usage
    WHERE api_key_id = p_api_key_id
      AND created_at > DATE_TRUNC('day', NOW());

    -- Check limits
    IF v_minute_count >= v_key.rate_limit_per_minute THEN
        RETURN QUERY SELECT
            FALSE,
            v_minute_count,
            v_day_count,
            v_key.rate_limit_per_minute,
            v_key.rate_limit_per_day,
            60 - EXTRACT(SECOND FROM NOW())::INTEGER;
        RETURN;
    END IF;

    IF v_day_count >= v_key.rate_limit_per_day THEN
        RETURN QUERY SELECT
            FALSE,
            v_minute_count,
            v_day_count,
            v_key.rate_limit_per_minute,
            v_key.rate_limit_per_day,
            EXTRACT(EPOCH FROM (DATE_TRUNC('day', NOW()) + INTERVAL '1 day' - NOW()))::INTEGER;
        RETURN;
    END IF;

    -- Allowed
    RETURN QUERY SELECT
        TRUE,
        v_minute_count,
        v_day_count,
        v_key.rate_limit_per_minute,
        v_key.rate_limit_per_day,
        0;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- FUNCTION: record_api_key_usage - Logs API request for analytics
-- ============================================================================

CREATE OR REPLACE FUNCTION record_api_key_usage(
    p_api_key_id UUID,
    p_user_id TEXT,
    p_endpoint TEXT,
    p_method TEXT,
    p_status_code INTEGER,
    p_tokens_in INTEGER DEFAULT 0,
    p_tokens_out INTEGER DEFAULT 0,
    p_cost_usd FLOAT DEFAULT 0,
    p_latency_ms FLOAT DEFAULT NULL,
    p_ip_address INET DEFAULT NULL,
    p_user_agent TEXT DEFAULT NULL,
    p_request_id TEXT DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_usage_id UUID;
BEGIN
    INSERT INTO api_key_usage (
        api_key_id, user_id, endpoint, method, status_code,
        tokens_in, tokens_out, cost_usd, latency_ms,
        ip_address, user_agent, request_id
    ) VALUES (
        p_api_key_id, p_user_id, p_endpoint, p_method, p_status_code,
        p_tokens_in, p_tokens_out, p_cost_usd, p_latency_ms,
        p_ip_address, p_user_agent, p_request_id
    )
    RETURNING id INTO v_usage_id;

    RETURN v_usage_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- FUNCTION: get_api_key_stats - Usage statistics for a key
-- ============================================================================

CREATE OR REPLACE FUNCTION get_api_key_stats(
    p_api_key_id UUID,
    p_days INTEGER DEFAULT 30
)
RETURNS TABLE (
    total_requests BIGINT,
    total_tokens_in BIGINT,
    total_tokens_out BIGINT,
    total_cost_usd FLOAT,
    avg_latency_ms FLOAT,
    success_rate FLOAT,
    requests_by_endpoint JSONB,
    requests_by_day JSONB
) AS $$
BEGIN
    RETURN QUERY
    WITH usage_data AS (
        SELECT * FROM api_key_usage
        WHERE api_key_id = p_api_key_id
          AND created_at > NOW() - (p_days || ' days')::INTERVAL
    ),
    by_endpoint AS (
        SELECT endpoint, COUNT(*) as cnt
        FROM usage_data
        GROUP BY endpoint
    ),
    by_day AS (
        SELECT DATE(created_at) as day, COUNT(*) as cnt
        FROM usage_data
        GROUP BY DATE(created_at)
        ORDER BY day
    )
    SELECT
        COUNT(*)::BIGINT as total_requests,
        COALESCE(SUM(tokens_in), 0)::BIGINT as total_tokens_in,
        COALESCE(SUM(tokens_out), 0)::BIGINT as total_tokens_out,
        COALESCE(SUM(cost_usd), 0)::FLOAT as total_cost_usd,
        AVG(latency_ms)::FLOAT as avg_latency_ms,
        (COUNT(*) FILTER (WHERE status_code < 400)::FLOAT / NULLIF(COUNT(*), 0))::FLOAT as success_rate,
        (SELECT jsonb_object_agg(endpoint, cnt) FROM by_endpoint) as requests_by_endpoint,
        (SELECT jsonb_agg(jsonb_build_object('day', day, 'count', cnt)) FROM by_day) as requests_by_day
    FROM usage_data;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- ROW LEVEL SECURITY POLICIES
-- ============================================================================

-- Enable RLS on both tables
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_key_usage ENABLE ROW LEVEL SECURITY;

-- API Keys policies: Users can only manage their own keys
CREATE POLICY api_keys_select_own ON api_keys
    FOR SELECT USING (user_id = current_setting('request.jwt.claims', true)::json->>'sub');

CREATE POLICY api_keys_insert_own ON api_keys
    FOR INSERT WITH CHECK (user_id = current_setting('request.jwt.claims', true)::json->>'sub');

CREATE POLICY api_keys_update_own ON api_keys
    FOR UPDATE USING (user_id = current_setting('request.jwt.claims', true)::json->>'sub');

CREATE POLICY api_keys_delete_own ON api_keys
    FOR DELETE USING (user_id = current_setting('request.jwt.claims', true)::json->>'sub');

-- API Key Usage policies: Users can only see usage for their own keys
CREATE POLICY api_key_usage_select_own ON api_key_usage
    FOR SELECT USING (user_id = current_setting('request.jwt.claims', true)::json->>'sub');

CREATE POLICY api_key_usage_insert_own ON api_key_usage
    FOR INSERT WITH CHECK (user_id = current_setting('request.jwt.claims', true)::json->>'sub');

-- ============================================================================
-- TRIGGER: Update updated_at on api_keys modification
-- ============================================================================

CREATE OR REPLACE FUNCTION update_api_keys_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_api_keys_updated_at
    BEFORE UPDATE ON api_keys
    FOR EACH ROW
    EXECUTE FUNCTION update_api_keys_updated_at();

-- ============================================================================
-- Verification
-- ============================================================================

SELECT '✅ API KEYS TABLES AND FUNCTIONS CREATED!' as status;

-- Show created objects
SELECT
    'Table' as type,
    table_name as name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('api_keys', 'api_key_usage')
UNION ALL
SELECT
    'Function' as type,
    routine_name as name
FROM information_schema.routines
WHERE routine_schema = 'public'
  AND routine_name IN ('validate_api_key', 'check_rate_limit', 'record_api_key_usage', 'get_api_key_stats')
ORDER BY type, name;
