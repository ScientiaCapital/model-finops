-- ============================================================================
-- Subscription Tracking Migration
-- Track all your SaaS subscriptions, billing dates, and costs
-- ============================================================================

-- Subscription status enum
CREATE TYPE subscription_status AS ENUM (
    'active',
    'trial',
    'cancelled',
    'paused',
    'past_due'
);

-- Billing cycle enum
CREATE TYPE billing_cycle AS ENUM (
    'monthly',
    'yearly',
    'quarterly',
    'weekly',
    'one_time',
    'usage_based'
);

-- Service category enum (matches our provider categories)
CREATE TYPE service_category AS ENUM (
    'llm_provider',
    'voice_tts',
    'voice_stt',
    'infrastructure',
    'ai_media',
    'observability',
    'billing',
    'other'
);

-- ============================================================================
-- Subscriptions Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

    -- Service identification
    service_name TEXT NOT NULL,                    -- e.g., "Anthropic", "Vercel"
    service_provider TEXT,                         -- Provider key from our registry
    category service_category DEFAULT 'other',

    -- Pricing
    monthly_cost DECIMAL(10, 2) NOT NULL DEFAULT 0,  -- Normalized to monthly
    original_price DECIMAL(10, 2),                    -- Original price
    currency TEXT DEFAULT 'USD',
    billing_cycle billing_cycle DEFAULT 'monthly',

    -- Billing dates
    billing_day INTEGER CHECK (billing_day >= 1 AND billing_day <= 31),  -- Day of month
    next_billing_date DATE,
    trial_ends_at TIMESTAMPTZ,

    -- Status
    status subscription_status DEFAULT 'active',
    auto_renew BOOLEAN DEFAULT true,

    -- Alerts
    alert_days_before INTEGER DEFAULT 3,           -- Days before billing to alert
    alert_enabled BOOLEAN DEFAULT true,
    last_alert_sent_at TIMESTAMPTZ,

    -- Metadata
    notes TEXT,
    api_key_configured BOOLEAN DEFAULT false,      -- Linked to our API key system
    external_subscription_id TEXT,                 -- ID from the service (Stripe, etc.)
    external_customer_id TEXT,

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Unique constraint: one subscription per service per user
    UNIQUE(user_id, service_name)
);

-- ============================================================================
-- Subscription Usage Table (for usage-based billing tracking)
-- ============================================================================
CREATE TABLE IF NOT EXISTS subscription_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id UUID NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

    -- Usage period
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,

    -- Usage metrics
    usage_amount DECIMAL(15, 6) NOT NULL DEFAULT 0,
    usage_unit TEXT DEFAULT 'tokens',              -- tokens, minutes, requests, etc.

    -- Cost
    cost_usd DECIMAL(10, 4) NOT NULL DEFAULT 0,

    -- Metadata
    breakdown JSONB,                               -- Detailed breakdown by model/service

    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- One record per subscription per period
    UNIQUE(subscription_id, period_start, period_end)
);

-- ============================================================================
-- Subscription Alerts Table (track sent alerts)
-- ============================================================================
CREATE TABLE IF NOT EXISTS subscription_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id UUID NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

    alert_type TEXT NOT NULL,                      -- 'billing_reminder', 'trial_ending', 'payment_failed'
    message TEXT,

    -- Delivery
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    channels TEXT[] DEFAULT '{}',                  -- ['email', 'slack', 'webhook']
    delivery_status TEXT DEFAULT 'sent',

    -- Reference
    billing_date DATE,
    amount DECIMAL(10, 2)
);

-- ============================================================================
-- Indexes
-- ============================================================================
CREATE INDEX idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX idx_subscriptions_status ON subscriptions(status);
CREATE INDEX idx_subscriptions_next_billing ON subscriptions(next_billing_date);
CREATE INDEX idx_subscriptions_category ON subscriptions(category);
CREATE INDEX idx_subscription_usage_subscription ON subscription_usage(subscription_id);
CREATE INDEX idx_subscription_usage_period ON subscription_usage(period_start, period_end);
CREATE INDEX idx_subscription_alerts_subscription ON subscription_alerts(subscription_id);

-- ============================================================================
-- Row Level Security
-- ============================================================================
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscription_usage ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscription_alerts ENABLE ROW LEVEL SECURITY;

-- Subscriptions policies
CREATE POLICY subscriptions_select ON subscriptions
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY subscriptions_insert ON subscriptions
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY subscriptions_update ON subscriptions
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY subscriptions_delete ON subscriptions
    FOR DELETE USING (auth.uid() = user_id);

-- Usage policies
CREATE POLICY subscription_usage_select ON subscription_usage
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY subscription_usage_insert ON subscription_usage
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Alerts policies
CREATE POLICY subscription_alerts_select ON subscription_alerts
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY subscription_alerts_insert ON subscription_alerts
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- ============================================================================
-- Functions
-- ============================================================================

-- Calculate next billing date based on billing day
CREATE OR REPLACE FUNCTION calculate_next_billing_date(
    p_billing_day INTEGER,
    p_billing_cycle billing_cycle
) RETURNS DATE AS $$
DECLARE
    v_today DATE := CURRENT_DATE;
    v_next_date DATE;
    v_days_in_month INTEGER;
BEGIN
    IF p_billing_cycle = 'monthly' THEN
        -- Get the billing day for this month (handle months with fewer days)
        v_days_in_month := EXTRACT(DAY FROM (DATE_TRUNC('month', v_today) + INTERVAL '1 month - 1 day'));

        IF p_billing_day > v_days_in_month THEN
            v_next_date := DATE_TRUNC('month', v_today) + (v_days_in_month - 1) * INTERVAL '1 day';
        ELSE
            v_next_date := DATE_TRUNC('month', v_today) + (p_billing_day - 1) * INTERVAL '1 day';
        END IF;

        -- If already passed this month, go to next month
        IF v_next_date <= v_today THEN
            v_next_date := v_next_date + INTERVAL '1 month';
        END IF;

    ELSIF p_billing_cycle = 'yearly' THEN
        v_next_date := DATE_TRUNC('year', v_today) + (p_billing_day - 1) * INTERVAL '1 day';
        IF v_next_date <= v_today THEN
            v_next_date := v_next_date + INTERVAL '1 year';
        END IF;

    ELSE
        v_next_date := v_today + INTERVAL '1 month';
    END IF;

    RETURN v_next_date;
END;
$$ LANGUAGE plpgsql;

-- Get subscriptions due for billing alert
CREATE OR REPLACE FUNCTION get_upcoming_billing_alerts(
    p_user_id UUID DEFAULT NULL
) RETURNS TABLE (
    subscription_id UUID,
    user_id UUID,
    service_name TEXT,
    monthly_cost DECIMAL,
    next_billing_date DATE,
    days_until_billing INTEGER,
    alert_days_before INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        s.id,
        s.user_id,
        s.service_name,
        s.monthly_cost,
        s.next_billing_date,
        (s.next_billing_date - CURRENT_DATE)::INTEGER AS days_until,
        s.alert_days_before
    FROM subscriptions s
    WHERE s.status = 'active'
      AND s.alert_enabled = true
      AND s.next_billing_date IS NOT NULL
      AND (s.next_billing_date - CURRENT_DATE) <= s.alert_days_before
      AND (s.next_billing_date - CURRENT_DATE) >= 0
      AND (p_user_id IS NULL OR s.user_id = p_user_id)
      AND (
          s.last_alert_sent_at IS NULL
          OR s.last_alert_sent_at < CURRENT_DATE - INTERVAL '1 day'
      )
    ORDER BY s.next_billing_date;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Get monthly spend summary
CREATE OR REPLACE FUNCTION get_monthly_spend_summary(
    p_user_id UUID
) RETURNS TABLE (
    total_monthly_cost DECIMAL,
    total_yearly_cost DECIMAL,
    active_subscriptions INTEGER,
    by_category JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COALESCE(SUM(s.monthly_cost), 0) AS total_monthly_cost,
        COALESCE(SUM(s.monthly_cost * 12), 0) AS total_yearly_cost,
        COUNT(*)::INTEGER AS active_subscriptions,
        COALESCE(
            jsonb_object_agg(
                s.category::TEXT,
                cat_totals.category_cost
            ),
            '{}'::JSONB
        ) AS by_category
    FROM subscriptions s
    LEFT JOIN (
        SELECT
            category,
            SUM(monthly_cost) AS category_cost
        FROM subscriptions
        WHERE user_id = p_user_id AND status = 'active'
        GROUP BY category
    ) cat_totals ON s.category = cat_totals.category
    WHERE s.user_id = p_user_id AND s.status = 'active';
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- Triggers
-- ============================================================================

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_subscription_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER subscriptions_updated_at
    BEFORE UPDATE ON subscriptions
    FOR EACH ROW
    EXECUTE FUNCTION update_subscription_timestamp();

-- Auto-calculate next billing date on insert/update
CREATE OR REPLACE FUNCTION auto_calculate_next_billing()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.billing_day IS NOT NULL AND NEW.next_billing_date IS NULL THEN
        NEW.next_billing_date := calculate_next_billing_date(NEW.billing_day, NEW.billing_cycle);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER subscriptions_auto_billing_date
    BEFORE INSERT OR UPDATE ON subscriptions
    FOR EACH ROW
    EXECUTE FUNCTION auto_calculate_next_billing();

-- ============================================================================
-- Seed data: Common services with typical pricing
-- ============================================================================
COMMENT ON TABLE subscriptions IS 'Track SaaS subscriptions with billing dates and costs';
COMMENT ON COLUMN subscriptions.billing_day IS 'Day of month when billing occurs (1-31)';
COMMENT ON COLUMN subscriptions.monthly_cost IS 'Cost normalized to monthly (yearly/12, etc)';
COMMENT ON COLUMN subscriptions.alert_days_before IS 'Send alert this many days before billing';
