-- Migration: forecasting_001_tables
-- Creates tables for cost forecasting ML system
-- Features: Forecasts, anomalies, budget projections

-- ==============================================================================
-- ENUMS
-- ==============================================================================

-- Forecast methods available
CREATE TYPE forecast_method AS ENUM (
    'exp_smoothing',
    'moving_avg',
    'linear',
    'naive',
    'ensemble'
);

-- Anomaly severity levels
CREATE TYPE anomaly_severity AS ENUM (
    'low',      -- z > 2
    'medium',   -- z > 2.5
    'high',     -- z > 3
    'critical'  -- z > 4
);

-- Budget warning levels
CREATE TYPE budget_warning_level AS ENUM (
    'safe',
    'caution',
    'warning',
    'critical'
);

-- ==============================================================================
-- TABLES
-- ==============================================================================

-- Cached forecasts
-- Stores generated forecasts for quick retrieval
CREATE TABLE cost_forecasts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    provider TEXT,  -- NULL for aggregate forecasts
    forecast_date DATE NOT NULL,
    horizon_days INTEGER NOT NULL,
    method forecast_method NOT NULL,
    data_points_used INTEGER NOT NULL,
    confidence_level DECIMAL(3, 2) DEFAULT 0.95,
    quality_score DECIMAL(5, 4),  -- MAPE
    daily_predictions JSONB NOT NULL,  -- [{date, predicted, lower, upper}]
    total_predicted_cost DECIMAL(12, 4) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ DEFAULT now() + INTERVAL '24 hours'
);

-- Index for user + date lookups
CREATE INDEX idx_cost_forecasts_user_date ON cost_forecasts(user_id, forecast_date DESC);

-- Index for cleanup of expired forecasts
CREATE INDEX idx_cost_forecasts_expires ON cost_forecasts(expires_at);

-- Detected cost anomalies
CREATE TABLE cost_anomalies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    anomaly_date DATE NOT NULL,
    provider TEXT,  -- NULL for aggregate anomalies
    actual_cost DECIMAL(12, 4) NOT NULL,
    expected_cost DECIMAL(12, 4) NOT NULL,
    deviation_percent DECIMAL(8, 2) NOT NULL,
    z_score DECIMAL(6, 3) NOT NULL,
    severity anomaly_severity NOT NULL,
    acknowledged BOOLEAN DEFAULT false,
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by UUID REFERENCES auth.users(id),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Index for user anomaly lookups
CREATE INDEX idx_cost_anomalies_user ON cost_anomalies(user_id, anomaly_date DESC);

-- Index for unacknowledged anomalies
CREATE INDEX idx_cost_anomalies_unack ON cost_anomalies(user_id, acknowledged)
    WHERE acknowledged = false;

-- Index for severity filtering
CREATE INDEX idx_cost_anomalies_severity ON cost_anomalies(user_id, severity);

-- Budget projections
CREATE TABLE budget_projections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    monthly_budget DECIMAL(12, 4) NOT NULL,
    current_spend DECIMAL(12, 4) NOT NULL,
    percentage_used DECIMAL(5, 2) NOT NULL,
    daily_burn_rate DECIMAL(12, 4) NOT NULL,
    projected_exhaustion_date DATE,
    days_until_exhaustion INTEGER,
    confidence_percentage DECIMAL(5, 2) NOT NULL,
    warning_level budget_warning_level NOT NULL,
    recommendation TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Unique constraint: one active projection per user
CREATE UNIQUE INDEX idx_budget_projections_user_unique
    ON budget_projections(user_id)
    WHERE updated_at > now() - INTERVAL '1 hour';

-- Daily cost aggregates for forecasting
-- Pre-computed for efficient forecasting queries
CREATE TABLE daily_cost_aggregates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    cost_date DATE NOT NULL,
    provider TEXT,  -- NULL for total aggregate
    total_cost DECIMAL(12, 4) NOT NULL,
    request_count INTEGER NOT NULL DEFAULT 0,
    token_count INTEGER NOT NULL DEFAULT 0,
    avg_cost_per_request DECIMAL(10, 6),
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (user_id, cost_date, provider)
);

-- Index for time-range queries
CREATE INDEX idx_daily_cost_aggregates_range ON daily_cost_aggregates(user_id, cost_date DESC);

-- Index for provider filtering
CREATE INDEX idx_daily_cost_aggregates_provider ON daily_cost_aggregates(user_id, provider, cost_date DESC);

-- ==============================================================================
-- ROW LEVEL SECURITY
-- ==============================================================================

-- Enable RLS
ALTER TABLE cost_forecasts ENABLE ROW LEVEL SECURITY;
ALTER TABLE cost_anomalies ENABLE ROW LEVEL SECURITY;
ALTER TABLE budget_projections ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_cost_aggregates ENABLE ROW LEVEL SECURITY;

-- cost_forecasts: Users see only their own
CREATE POLICY "cost_forecasts_select" ON cost_forecasts
    FOR SELECT TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "cost_forecasts_insert" ON cost_forecasts
    FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "cost_forecasts_delete" ON cost_forecasts
    FOR DELETE TO authenticated
    USING (auth.uid() = user_id);

-- cost_anomalies: Users see only their own
CREATE POLICY "cost_anomalies_select" ON cost_anomalies
    FOR SELECT TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "cost_anomalies_insert" ON cost_anomalies
    FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "cost_anomalies_update" ON cost_anomalies
    FOR UPDATE TO authenticated
    USING (auth.uid() = user_id);

-- budget_projections: Users see only their own
CREATE POLICY "budget_projections_select" ON budget_projections
    FOR SELECT TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "budget_projections_insert" ON budget_projections
    FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "budget_projections_update" ON budget_projections
    FOR UPDATE TO authenticated
    USING (auth.uid() = user_id);

-- daily_cost_aggregates: Users see only their own
CREATE POLICY "daily_cost_aggregates_select" ON daily_cost_aggregates
    FOR SELECT TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "daily_cost_aggregates_insert" ON daily_cost_aggregates
    FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = user_id);

-- Service role can access everything (for background jobs)
CREATE POLICY "cost_forecasts_service" ON cost_forecasts
    FOR ALL TO service_role USING (true);

CREATE POLICY "cost_anomalies_service" ON cost_anomalies
    FOR ALL TO service_role USING (true);

CREATE POLICY "budget_projections_service" ON budget_projections
    FOR ALL TO service_role USING (true);

CREATE POLICY "daily_cost_aggregates_service" ON daily_cost_aggregates
    FOR ALL TO service_role USING (true);

-- ==============================================================================
-- FUNCTIONS
-- ==============================================================================

-- Function to aggregate daily costs from requests table
CREATE OR REPLACE FUNCTION aggregate_daily_costs(
    p_user_id UUID,
    p_date DATE
) RETURNS void AS $$
BEGIN
    -- Aggregate by provider
    INSERT INTO daily_cost_aggregates (user_id, cost_date, provider, total_cost, request_count, token_count, avg_cost_per_request)
    SELECT
        p_user_id,
        p_date,
        provider,
        SUM(total_cost),
        COUNT(*),
        SUM(total_tokens),
        AVG(total_cost)
    FROM requests
    WHERE user_id = p_user_id
      AND DATE(created_at) = p_date
    GROUP BY provider
    ON CONFLICT (user_id, cost_date, provider)
    DO UPDATE SET
        total_cost = EXCLUDED.total_cost,
        request_count = EXCLUDED.request_count,
        token_count = EXCLUDED.token_count,
        avg_cost_per_request = EXCLUDED.avg_cost_per_request;

    -- Aggregate total (NULL provider)
    INSERT INTO daily_cost_aggregates (user_id, cost_date, provider, total_cost, request_count, token_count, avg_cost_per_request)
    SELECT
        p_user_id,
        p_date,
        NULL,
        SUM(total_cost),
        COUNT(*),
        SUM(total_tokens),
        AVG(total_cost)
    FROM requests
    WHERE user_id = p_user_id
      AND DATE(created_at) = p_date
    ON CONFLICT (user_id, cost_date, provider)
    DO UPDATE SET
        total_cost = EXCLUDED.total_cost,
        request_count = EXCLUDED.request_count,
        token_count = EXCLUDED.token_count,
        avg_cost_per_request = EXCLUDED.avg_cost_per_request;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to detect anomalies using Z-score
CREATE OR REPLACE FUNCTION detect_cost_anomaly(
    p_user_id UUID,
    p_date DATE,
    p_sensitivity DECIMAL DEFAULT 2.0
) RETURNS TABLE (
    provider TEXT,
    actual_cost DECIMAL,
    expected_cost DECIMAL,
    z_score DECIMAL,
    severity anomaly_severity
) AS $$
BEGIN
    RETURN QUERY
    WITH historical AS (
        SELECT
            dca.provider,
            AVG(dca.total_cost) as avg_cost,
            STDDEV(dca.total_cost) as std_cost
        FROM daily_cost_aggregates dca
        WHERE dca.user_id = p_user_id
          AND dca.cost_date >= p_date - INTERVAL '30 days'
          AND dca.cost_date < p_date
        GROUP BY dca.provider
    ),
    current_day AS (
        SELECT
            dca.provider,
            dca.total_cost
        FROM daily_cost_aggregates dca
        WHERE dca.user_id = p_user_id
          AND dca.cost_date = p_date
    )
    SELECT
        cd.provider,
        cd.total_cost AS actual_cost,
        h.avg_cost AS expected_cost,
        CASE
            WHEN h.std_cost > 0 THEN (cd.total_cost - h.avg_cost) / h.std_cost
            ELSE 0
        END AS z_score,
        CASE
            WHEN ABS((cd.total_cost - h.avg_cost) / NULLIF(h.std_cost, 0)) > 4 THEN 'critical'::anomaly_severity
            WHEN ABS((cd.total_cost - h.avg_cost) / NULLIF(h.std_cost, 0)) > 3 THEN 'high'::anomaly_severity
            WHEN ABS((cd.total_cost - h.avg_cost) / NULLIF(h.std_cost, 0)) > 2.5 THEN 'medium'::anomaly_severity
            ELSE 'low'::anomaly_severity
        END AS severity
    FROM current_day cd
    JOIN historical h ON (cd.provider IS NOT DISTINCT FROM h.provider)
    WHERE ABS((cd.total_cost - h.avg_cost) / NULLIF(h.std_cost, 0)) > p_sensitivity;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get user's historical costs for forecasting
CREATE OR REPLACE FUNCTION get_forecast_data(
    p_user_id UUID,
    p_provider TEXT DEFAULT NULL,
    p_days INTEGER DEFAULT 30
) RETURNS TABLE (
    cost_date DATE,
    total_cost DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        dca.cost_date,
        dca.total_cost
    FROM daily_cost_aggregates dca
    WHERE dca.user_id = p_user_id
      AND (p_provider IS NULL AND dca.provider IS NULL OR dca.provider = p_provider)
      AND dca.cost_date >= CURRENT_DATE - p_days
    ORDER BY dca.cost_date ASC;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to clean up expired forecasts
CREATE OR REPLACE FUNCTION cleanup_expired_forecasts() RETURNS void AS $$
BEGIN
    DELETE FROM cost_forecasts WHERE expires_at < now();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ==============================================================================
-- TRIGGERS
-- ==============================================================================

-- Update timestamp trigger for budget_projections
CREATE TRIGGER update_budget_projections_modtime
    BEFORE UPDATE ON budget_projections
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();

-- ==============================================================================
-- COMMENTS
-- ==============================================================================

COMMENT ON TABLE cost_forecasts IS 'Cached cost predictions with confidence intervals';
COMMENT ON TABLE cost_anomalies IS 'Detected unusual spending patterns flagged for review';
COMMENT ON TABLE budget_projections IS 'Current budget exhaustion projections and warnings';
COMMENT ON TABLE daily_cost_aggregates IS 'Pre-computed daily cost totals for efficient forecasting';
COMMENT ON FUNCTION aggregate_daily_costs(UUID, DATE) IS 'Aggregates request costs into daily totals';
COMMENT ON FUNCTION detect_cost_anomaly(UUID, DATE, DECIMAL) IS 'Detects spending anomalies using Z-score';
COMMENT ON FUNCTION get_forecast_data(UUID, TEXT, INTEGER) IS 'Retrieves historical costs for forecasting';
