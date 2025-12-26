-- Migration: Budget Alerting System
-- Creates tables for budget configuration and alert tracking

-- Budget configurations per user
CREATE TABLE IF NOT EXISTS budget_configurations (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL,
    monthly_budget FLOAT NOT NULL DEFAULT 100.0,
    alert_thresholds FLOAT[] NOT NULL DEFAULT '{0.5,0.8,0.9}',
    alert_email TEXT,
    alert_webhook_url TEXT,
    slack_webhook_url TEXT,
    discord_webhook_url TEXT,
    alert_cooldown_minutes INT NOT NULL DEFAULT 60,
    enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id)
);

-- Alert history for audit trail and preventing spam
CREATE TABLE IF NOT EXISTS budget_alerts_sent (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL,
    threshold_percentage FLOAT NOT NULL,
    current_spend FLOAT NOT NULL,
    monthly_budget FLOAT NOT NULL,
    alert_channels TEXT[] NOT NULL,
    status TEXT NOT NULL DEFAULT 'sent',
    error_message TEXT,
    sent_at TIMESTAMPTZ DEFAULT NOW()
);

-- Daily cost rollups for efficient budget checking
CREATE TABLE IF NOT EXISTS daily_cost_summary (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL,
    date DATE NOT NULL,
    total_cost FLOAT NOT NULL DEFAULT 0.0,
    total_requests INT NOT NULL DEFAULT 0,
    cache_hits INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, date)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_budget_configs_user ON budget_configurations(user_id);
CREATE INDEX IF NOT EXISTS idx_alerts_sent_user_date ON budget_alerts_sent(user_id, sent_at DESC);
CREATE INDEX IF NOT EXISTS idx_daily_cost_user_date ON daily_cost_summary(user_id, date DESC);

-- RLS Policies
ALTER TABLE budget_configurations ENABLE ROW LEVEL SECURITY;
ALTER TABLE budget_alerts_sent ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_cost_summary ENABLE ROW LEVEL SECURITY;

-- Users can manage their own budget config
CREATE POLICY "Users can view own budget config"
    ON budget_configurations FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own budget config"
    ON budget_configurations FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own budget config"
    ON budget_configurations FOR UPDATE
    USING (auth.uid() = user_id);

-- Users can view their own alert history
CREATE POLICY "Users can view own alert history"
    ON budget_alerts_sent FOR SELECT
    USING (auth.uid() = user_id);

-- Service role can insert alerts
CREATE POLICY "Service can insert alerts"
    ON budget_alerts_sent FOR INSERT
    WITH CHECK (true);

-- Users can view their own daily summaries
CREATE POLICY "Users can view own daily summaries"
    ON daily_cost_summary FOR SELECT
    USING (auth.uid() = user_id);

-- Service role can manage daily summaries
CREATE POLICY "Service can manage daily summaries"
    ON daily_cost_summary FOR ALL
    USING (true);

-- Function to get current month's spend
CREATE OR REPLACE FUNCTION get_monthly_spend(p_user_id UUID)
RETURNS FLOAT AS $$
DECLARE
    total_spend FLOAT;
BEGIN
    SELECT COALESCE(SUM(total_cost), 0.0)
    INTO total_spend
    FROM daily_cost_summary
    WHERE user_id = p_user_id
      AND date >= date_trunc('month', CURRENT_DATE)::DATE;

    RETURN total_spend;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to check if alert was recently sent (cooldown check)
CREATE OR REPLACE FUNCTION should_send_alert(
    p_user_id UUID,
    p_threshold FLOAT,
    p_cooldown_minutes INT DEFAULT 60
)
RETURNS BOOLEAN AS $$
DECLARE
    last_alert_time TIMESTAMPTZ;
BEGIN
    SELECT MAX(sent_at)
    INTO last_alert_time
    FROM budget_alerts_sent
    WHERE user_id = p_user_id
      AND threshold_percentage = p_threshold
      AND status = 'sent';

    IF last_alert_time IS NULL THEN
        RETURN true;
    END IF;

    RETURN (NOW() - last_alert_time) > (p_cooldown_minutes || ' minutes')::INTERVAL;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant permissions
GRANT EXECUTE ON FUNCTION get_monthly_spend(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION should_send_alert(UUID, FLOAT, INT) TO authenticated;
GRANT EXECUTE ON FUNCTION get_monthly_spend(UUID) TO service_role;
GRANT EXECUTE ON FUNCTION should_send_alert(UUID, FLOAT, INT) TO service_role;

COMMENT ON TABLE budget_configurations IS 'Per-user budget settings and notification preferences';
COMMENT ON TABLE budget_alerts_sent IS 'Audit trail of all budget alerts sent';
COMMENT ON TABLE daily_cost_summary IS 'Daily rollup of costs for efficient budget checking';
