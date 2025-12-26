-- =============================================================================
-- Stripe Billing Integration
--
-- Multi-tenant billing system with subscription tiers, usage tracking,
-- and Stripe webhook event logging.
--
-- Tables:
--   - customers: Links Supabase auth users to Stripe customer IDs
--   - subscriptions: Active subscription state per user
--   - usage_records: Monthly token consumption tracking
--   - billing_events: Webhook audit log for debugging
--   - invoices: Invoice history cache
--
-- Functions:
--   - get_tier_limits(tier): Returns quota and features for a tier
--   - get_current_usage(user_id): Returns current period usage stats
--   - increment_usage(user_id, tokens): Atomically increment usage
--   - check_quota(user_id): Check if user has remaining quota
--
-- Run this migration after 20241226000007_api_keys.sql
-- =============================================================================

-- =============================================================================
-- ENUM Types
-- =============================================================================

-- Subscription tier levels
CREATE TYPE subscription_tier AS ENUM (
    'free',        -- 10,000 tokens/month, basic routing
    'pro',         -- 1,000,000 tokens/month, A/B testing
    'business',    -- 10,000,000 tokens/month, priority routing
    'enterprise'   -- Unlimited tokens, dedicated support
);

-- Subscription status (mirrors Stripe statuses)
CREATE TYPE subscription_status AS ENUM (
    'active',       -- Currently active and paid
    'past_due',     -- Payment failed, grace period
    'canceled',     -- User canceled, access until period end
    'trialing',     -- In free trial period
    'incomplete',   -- Initial payment pending
    'paused'        -- Temporarily paused by admin
);

-- Billing event types for webhook logging
CREATE TYPE billing_event_type AS ENUM (
    'checkout.session.completed',
    'customer.created',
    'customer.updated',
    'customer.deleted',
    'customer.subscription.created',
    'customer.subscription.updated',
    'customer.subscription.deleted',
    'invoice.created',
    'invoice.paid',
    'invoice.payment_failed',
    'invoice.finalized',
    'payment_intent.succeeded',
    'payment_intent.payment_failed',
    'charge.succeeded',
    'charge.failed',
    'charge.refunded'
);


-- =============================================================================
-- Tier Limits Configuration Table
-- =============================================================================

CREATE TABLE tier_limits (
    tier subscription_tier PRIMARY KEY,
    monthly_token_limit BIGINT NOT NULL,
    monthly_request_limit INTEGER,
    rate_limit_per_minute INTEGER NOT NULL DEFAULT 60,
    rate_limit_per_day INTEGER NOT NULL DEFAULT 10000,
    features JSONB NOT NULL DEFAULT '{}',
    price_usd_monthly DECIMAL(10, 2),
    stripe_price_id TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert default tier configurations
INSERT INTO tier_limits (tier, monthly_token_limit, monthly_request_limit, rate_limit_per_minute, rate_limit_per_day, features, price_usd_monthly) VALUES
    ('free', 10000, 100, 10, 100,
     '{"routing": true, "caching": true, "ab_testing": false, "priority_routing": false, "custom_models": false}'::jsonb,
     0.00),
    ('pro', 1000000, 10000, 60, 10000,
     '{"routing": true, "caching": true, "ab_testing": true, "priority_routing": false, "custom_models": false}'::jsonb,
     49.00),
    ('business', 10000000, 100000, 300, 100000,
     '{"routing": true, "caching": true, "ab_testing": true, "priority_routing": true, "custom_models": true}'::jsonb,
     299.00),
    ('enterprise', 9223372036854775807, NULL, 1000, 1000000,
     '{"routing": true, "caching": true, "ab_testing": true, "priority_routing": true, "custom_models": true, "dedicated_support": true, "sla": true}'::jsonb,
     NULL);  -- Custom pricing


-- =============================================================================
-- Customers Table
-- =============================================================================

CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    stripe_customer_id TEXT UNIQUE NOT NULL,
    email TEXT NOT NULL,
    name TEXT,

    -- Default payment method
    default_payment_method_id TEXT,

    -- Billing address (optional)
    billing_address JSONB,

    -- Tax information
    tax_id TEXT,
    tax_exempt BOOLEAN DEFAULT FALSE,

    -- Metadata
    metadata JSONB DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Ensure one customer record per user
    CONSTRAINT unique_user_customer UNIQUE (user_id)
);

-- Index for fast lookups
CREATE INDEX idx_customers_stripe_id ON customers(stripe_customer_id);
CREATE INDEX idx_customers_user_id ON customers(user_id);
CREATE INDEX idx_customers_email ON customers(email);


-- =============================================================================
-- Subscriptions Table
-- =============================================================================

CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    customer_id UUID REFERENCES customers(id) ON DELETE SET NULL,
    stripe_subscription_id TEXT UNIQUE NOT NULL,
    stripe_price_id TEXT NOT NULL,

    -- Subscription state
    tier subscription_tier NOT NULL DEFAULT 'free',
    status subscription_status NOT NULL DEFAULT 'active',

    -- Billing period
    current_period_start TIMESTAMP WITH TIME ZONE NOT NULL,
    current_period_end TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Trial information
    trial_start TIMESTAMP WITH TIME ZONE,
    trial_end TIMESTAMP WITH TIME ZONE,

    -- Cancellation info
    cancel_at_period_end BOOLEAN DEFAULT FALSE,
    canceled_at TIMESTAMP WITH TIME ZONE,
    cancellation_reason TEXT,

    -- Quantity (for per-seat pricing if needed)
    quantity INTEGER DEFAULT 1,

    -- Metadata
    metadata JSONB DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Ensure one active subscription per user
    -- (allows historical records but only one non-canceled)
    CONSTRAINT unique_active_subscription UNIQUE (user_id, stripe_subscription_id)
);

-- Indexes for common queries
CREATE INDEX idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX idx_subscriptions_stripe_id ON subscriptions(stripe_subscription_id);
CREATE INDEX idx_subscriptions_status ON subscriptions(status);
CREATE INDEX idx_subscriptions_tier ON subscriptions(tier);
CREATE INDEX idx_subscriptions_period ON subscriptions(current_period_start, current_period_end);


-- =============================================================================
-- Usage Records Table
-- =============================================================================

CREATE TABLE usage_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    subscription_id UUID REFERENCES subscriptions(id) ON DELETE SET NULL,

    -- Billing period (monthly buckets)
    period_start TIMESTAMP WITH TIME ZONE NOT NULL,
    period_end TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Token usage
    tokens_used BIGINT NOT NULL DEFAULT 0,
    tokens_limit BIGINT NOT NULL,

    -- Request counts
    requests_count INTEGER NOT NULL DEFAULT 0,
    requests_limit INTEGER,

    -- Cost tracking (in cents for precision)
    estimated_cost_cents INTEGER NOT NULL DEFAULT 0,
    actual_cost_cents INTEGER DEFAULT 0,
    savings_cents INTEGER DEFAULT 0,

    -- Breakdown by provider
    usage_by_provider JSONB DEFAULT '{}',

    -- Breakdown by model
    usage_by_model JSONB DEFAULT '{}',

    -- Cache performance
    cache_hits INTEGER DEFAULT 0,
    cache_misses INTEGER DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Ensure one record per user per period
    CONSTRAINT unique_user_period UNIQUE (user_id, period_start)
);

-- Indexes for usage queries
CREATE INDEX idx_usage_records_user_id ON usage_records(user_id);
CREATE INDEX idx_usage_records_period ON usage_records(period_start, period_end);
CREATE INDEX idx_usage_records_subscription ON usage_records(subscription_id);


-- =============================================================================
-- Billing Events Table (Webhook Audit Log)
-- =============================================================================

CREATE TABLE billing_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stripe_event_id TEXT UNIQUE NOT NULL,
    event_type billing_event_type NOT NULL,

    -- Associated resources
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    customer_id UUID REFERENCES customers(id) ON DELETE SET NULL,
    subscription_id UUID REFERENCES subscriptions(id) ON DELETE SET NULL,

    -- Stripe resource IDs for reference
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    stripe_invoice_id TEXT,
    stripe_payment_intent_id TEXT,

    -- Full event payload for debugging
    payload JSONB NOT NULL,

    -- Processing status
    processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Idempotency - prevent duplicate processing
    CONSTRAINT unique_stripe_event UNIQUE (stripe_event_id)
);

-- Indexes for event queries
CREATE INDEX idx_billing_events_type ON billing_events(event_type);
CREATE INDEX idx_billing_events_user_id ON billing_events(user_id);
CREATE INDEX idx_billing_events_processed ON billing_events(processed);
CREATE INDEX idx_billing_events_created ON billing_events(created_at DESC);


-- =============================================================================
-- Invoices Table
-- =============================================================================

CREATE TABLE invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    customer_id UUID REFERENCES customers(id) ON DELETE SET NULL,
    subscription_id UUID REFERENCES subscriptions(id) ON DELETE SET NULL,

    -- Stripe references
    stripe_invoice_id TEXT UNIQUE NOT NULL,
    stripe_hosted_invoice_url TEXT,
    stripe_pdf_url TEXT,

    -- Invoice details
    invoice_number TEXT,
    status TEXT NOT NULL,  -- draft, open, paid, void, uncollectible

    -- Amounts (in cents)
    subtotal_cents INTEGER NOT NULL,
    tax_cents INTEGER DEFAULT 0,
    total_cents INTEGER NOT NULL,
    amount_paid_cents INTEGER DEFAULT 0,
    amount_due_cents INTEGER DEFAULT 0,

    -- Currency
    currency TEXT NOT NULL DEFAULT 'usd',

    -- Period this invoice covers
    period_start TIMESTAMP WITH TIME ZONE,
    period_end TIMESTAMP WITH TIME ZONE,

    -- Payment dates
    due_date TIMESTAMP WITH TIME ZONE,
    paid_at TIMESTAMP WITH TIME ZONE,

    -- Line items summary
    line_items JSONB DEFAULT '[]',

    -- Metadata
    metadata JSONB DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for invoice queries
CREATE INDEX idx_invoices_user_id ON invoices(user_id);
CREATE INDEX idx_invoices_stripe_id ON invoices(stripe_invoice_id);
CREATE INDEX idx_invoices_status ON invoices(status);
CREATE INDEX idx_invoices_created ON invoices(created_at DESC);


-- =============================================================================
-- Functions
-- =============================================================================

-- Get tier limits by tier name
CREATE OR REPLACE FUNCTION get_tier_limits(p_tier subscription_tier)
RETURNS TABLE (
    tier subscription_tier,
    monthly_token_limit BIGINT,
    monthly_request_limit INTEGER,
    rate_limit_per_minute INTEGER,
    rate_limit_per_day INTEGER,
    features JSONB,
    price_usd_monthly DECIMAL(10, 2)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        tl.tier,
        tl.monthly_token_limit,
        tl.monthly_request_limit,
        tl.rate_limit_per_minute,
        tl.rate_limit_per_day,
        tl.features,
        tl.price_usd_monthly
    FROM tier_limits tl
    WHERE tl.tier = p_tier;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;


-- Get user's current subscription and tier
CREATE OR REPLACE FUNCTION get_user_subscription(p_user_id UUID)
RETURNS TABLE (
    subscription_id UUID,
    tier subscription_tier,
    status subscription_status,
    current_period_start TIMESTAMP WITH TIME ZONE,
    current_period_end TIMESTAMP WITH TIME ZONE,
    cancel_at_period_end BOOLEAN,
    monthly_token_limit BIGINT,
    features JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        s.id,
        s.tier,
        s.status,
        s.current_period_start,
        s.current_period_end,
        s.cancel_at_period_end,
        tl.monthly_token_limit,
        tl.features
    FROM subscriptions s
    JOIN tier_limits tl ON s.tier = tl.tier
    WHERE s.user_id = p_user_id
      AND s.status IN ('active', 'trialing', 'past_due')
    ORDER BY s.created_at DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;


-- Get or create current period usage record
CREATE OR REPLACE FUNCTION get_or_create_usage_record(p_user_id UUID)
RETURNS usage_records AS $$
DECLARE
    v_record usage_records;
    v_period_start TIMESTAMP WITH TIME ZONE;
    v_period_end TIMESTAMP WITH TIME ZONE;
    v_subscription subscriptions;
    v_limits tier_limits;
BEGIN
    -- Calculate current billing period (monthly, starting on 1st)
    v_period_start := date_trunc('month', NOW());
    v_period_end := v_period_start + INTERVAL '1 month';

    -- Try to get existing record
    SELECT * INTO v_record
    FROM usage_records
    WHERE user_id = p_user_id
      AND period_start = v_period_start;

    IF v_record IS NOT NULL THEN
        RETURN v_record;
    END IF;

    -- Get user's subscription and tier limits
    SELECT * INTO v_subscription
    FROM subscriptions
    WHERE user_id = p_user_id
      AND status IN ('active', 'trialing', 'past_due')
    ORDER BY created_at DESC
    LIMIT 1;

    -- Default to free tier if no subscription
    SELECT * INTO v_limits
    FROM tier_limits
    WHERE tier = COALESCE(v_subscription.tier, 'free');

    -- Create new usage record
    INSERT INTO usage_records (
        user_id,
        subscription_id,
        period_start,
        period_end,
        tokens_limit,
        requests_limit
    ) VALUES (
        p_user_id,
        v_subscription.id,
        v_period_start,
        v_period_end,
        v_limits.monthly_token_limit,
        v_limits.monthly_request_limit
    )
    RETURNING * INTO v_record;

    RETURN v_record;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;


-- Increment usage atomically
CREATE OR REPLACE FUNCTION increment_usage(
    p_user_id UUID,
    p_tokens INTEGER,
    p_cost_cents INTEGER DEFAULT 0,
    p_provider TEXT DEFAULT NULL,
    p_model TEXT DEFAULT NULL,
    p_is_cache_hit BOOLEAN DEFAULT FALSE
)
RETURNS TABLE (
    tokens_used BIGINT,
    tokens_limit BIGINT,
    tokens_remaining BIGINT,
    is_over_limit BOOLEAN
) AS $$
DECLARE
    v_record usage_records;
BEGIN
    -- Get or create usage record for current period
    v_record := get_or_create_usage_record(p_user_id);

    -- Update usage atomically
    UPDATE usage_records
    SET
        tokens_used = usage_records.tokens_used + p_tokens,
        requests_count = requests_count + 1,
        estimated_cost_cents = estimated_cost_cents + p_cost_cents,
        cache_hits = cache_hits + CASE WHEN p_is_cache_hit THEN 1 ELSE 0 END,
        cache_misses = cache_misses + CASE WHEN p_is_cache_hit THEN 0 ELSE 1 END,
        usage_by_provider = CASE
            WHEN p_provider IS NOT NULL THEN
                jsonb_set(
                    COALESCE(usage_by_provider, '{}'::jsonb),
                    ARRAY[p_provider],
                    COALESCE(usage_by_provider->p_provider, '0')::jsonb::int + p_tokens || ''
                )
            ELSE usage_by_provider
        END,
        usage_by_model = CASE
            WHEN p_model IS NOT NULL THEN
                jsonb_set(
                    COALESCE(usage_by_model, '{}'::jsonb),
                    ARRAY[p_model],
                    COALESCE(usage_by_model->p_model, '0')::jsonb::int + p_tokens || ''
                )
            ELSE usage_by_model
        END,
        updated_at = NOW()
    WHERE id = v_record.id
    RETURNING usage_records.tokens_used, usage_records.tokens_limit INTO v_record.tokens_used, v_record.tokens_limit;

    RETURN QUERY
    SELECT
        v_record.tokens_used,
        v_record.tokens_limit,
        GREATEST(0, v_record.tokens_limit - v_record.tokens_used),
        v_record.tokens_used >= v_record.tokens_limit;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;


-- Check if user has remaining quota
CREATE OR REPLACE FUNCTION check_quota(p_user_id UUID)
RETURNS TABLE (
    has_quota BOOLEAN,
    tokens_used BIGINT,
    tokens_limit BIGINT,
    tokens_remaining BIGINT,
    usage_percentage DECIMAL(5, 2),
    tier subscription_tier,
    period_ends_at TIMESTAMP WITH TIME ZONE
) AS $$
DECLARE
    v_record usage_records;
    v_subscription subscriptions;
BEGIN
    -- Get current usage record
    v_record := get_or_create_usage_record(p_user_id);

    -- Get subscription info
    SELECT * INTO v_subscription
    FROM subscriptions
    WHERE user_id = p_user_id
      AND status IN ('active', 'trialing', 'past_due')
    ORDER BY created_at DESC
    LIMIT 1;

    RETURN QUERY
    SELECT
        v_record.tokens_used < v_record.tokens_limit,
        v_record.tokens_used,
        v_record.tokens_limit,
        GREATEST(0, v_record.tokens_limit - v_record.tokens_used),
        ROUND((v_record.tokens_used::DECIMAL / NULLIF(v_record.tokens_limit, 0)) * 100, 2),
        COALESCE(v_subscription.tier, 'free'::subscription_tier),
        v_record.period_end;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;


-- Get billing summary for user
CREATE OR REPLACE FUNCTION get_billing_summary(p_user_id UUID)
RETURNS TABLE (
    customer_id UUID,
    stripe_customer_id TEXT,
    subscription_id UUID,
    tier subscription_tier,
    status subscription_status,
    current_period_start TIMESTAMP WITH TIME ZONE,
    current_period_end TIMESTAMP WITH TIME ZONE,
    tokens_used BIGINT,
    tokens_limit BIGINT,
    usage_percentage DECIMAL(5, 2),
    estimated_cost_cents INTEGER,
    cancel_at_period_end BOOLEAN,
    next_invoice_date TIMESTAMP WITH TIME ZONE
) AS $$
DECLARE
    v_customer customers;
    v_subscription subscriptions;
    v_usage usage_records;
BEGIN
    -- Get customer
    SELECT * INTO v_customer
    FROM customers WHERE user_id = p_user_id;

    -- Get active subscription
    SELECT * INTO v_subscription
    FROM subscriptions
    WHERE user_id = p_user_id
      AND status IN ('active', 'trialing', 'past_due')
    ORDER BY created_at DESC
    LIMIT 1;

    -- Get current usage
    v_usage := get_or_create_usage_record(p_user_id);

    RETURN QUERY
    SELECT
        v_customer.id,
        v_customer.stripe_customer_id,
        v_subscription.id,
        COALESCE(v_subscription.tier, 'free'::subscription_tier),
        COALESCE(v_subscription.status, 'active'::subscription_status),
        v_usage.period_start,
        v_usage.period_end,
        v_usage.tokens_used,
        v_usage.tokens_limit,
        ROUND((v_usage.tokens_used::DECIMAL / NULLIF(v_usage.tokens_limit, 0)) * 100, 2),
        v_usage.estimated_cost_cents,
        COALESCE(v_subscription.cancel_at_period_end, FALSE),
        v_subscription.current_period_end;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;


-- =============================================================================
-- Triggers
-- =============================================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_billing_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_customers_updated
    BEFORE UPDATE ON customers
    FOR EACH ROW
    EXECUTE FUNCTION update_billing_timestamp();

CREATE TRIGGER trigger_subscriptions_updated
    BEFORE UPDATE ON subscriptions
    FOR EACH ROW
    EXECUTE FUNCTION update_billing_timestamp();

CREATE TRIGGER trigger_usage_records_updated
    BEFORE UPDATE ON usage_records
    FOR EACH ROW
    EXECUTE FUNCTION update_billing_timestamp();

CREATE TRIGGER trigger_invoices_updated
    BEFORE UPDATE ON invoices
    FOR EACH ROW
    EXECUTE FUNCTION update_billing_timestamp();


-- =============================================================================
-- Row-Level Security Policies
-- =============================================================================

-- Enable RLS on all billing tables
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE billing_events ENABLE ROW LEVEL SECURITY;

-- Customers: Users can only see their own customer record
CREATE POLICY customers_select_own ON customers
    FOR SELECT USING (user_id = auth.uid());

CREATE POLICY customers_insert_own ON customers
    FOR INSERT WITH CHECK (user_id = auth.uid());

CREATE POLICY customers_update_own ON customers
    FOR UPDATE USING (user_id = auth.uid());

-- Subscriptions: Users can only see their own subscriptions
CREATE POLICY subscriptions_select_own ON subscriptions
    FOR SELECT USING (user_id = auth.uid());

CREATE POLICY subscriptions_insert_own ON subscriptions
    FOR INSERT WITH CHECK (user_id = auth.uid());

CREATE POLICY subscriptions_update_own ON subscriptions
    FOR UPDATE USING (user_id = auth.uid());

-- Usage records: Users can only see their own usage
CREATE POLICY usage_records_select_own ON usage_records
    FOR SELECT USING (user_id = auth.uid());

CREATE POLICY usage_records_insert_own ON usage_records
    FOR INSERT WITH CHECK (user_id = auth.uid());

CREATE POLICY usage_records_update_own ON usage_records
    FOR UPDATE USING (user_id = auth.uid());

-- Invoices: Users can only see their own invoices
CREATE POLICY invoices_select_own ON invoices
    FOR SELECT USING (user_id = auth.uid());

CREATE POLICY invoices_insert_own ON invoices
    FOR INSERT WITH CHECK (user_id = auth.uid());

-- Billing events: Users can see events related to them
CREATE POLICY billing_events_select_own ON billing_events
    FOR SELECT USING (user_id = auth.uid());

-- Service role can do everything (for webhook processing)
CREATE POLICY customers_service_all ON customers
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY subscriptions_service_all ON subscriptions
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY usage_records_service_all ON usage_records
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY invoices_service_all ON invoices
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY billing_events_service_all ON billing_events
    FOR ALL USING (auth.role() = 'service_role');


-- =============================================================================
-- Default Free Subscription for New Users (Optional Trigger)
-- =============================================================================

-- Function to create free subscription when user signs up
CREATE OR REPLACE FUNCTION create_free_subscription_on_signup()
RETURNS TRIGGER AS $$
DECLARE
    v_period_start TIMESTAMP WITH TIME ZONE;
    v_period_end TIMESTAMP WITH TIME ZONE;
BEGIN
    v_period_start := date_trunc('month', NOW());
    v_period_end := v_period_start + INTERVAL '1 month';

    -- Create a free tier subscription
    INSERT INTO subscriptions (
        user_id,
        stripe_subscription_id,
        stripe_price_id,
        tier,
        status,
        current_period_start,
        current_period_end
    ) VALUES (
        NEW.id,
        'free_' || NEW.id::TEXT,  -- Placeholder ID for free tier
        'price_free',
        'free',
        'active',
        v_period_start,
        v_period_end
    );

    -- Create initial usage record
    INSERT INTO usage_records (
        user_id,
        period_start,
        period_end,
        tokens_limit,
        requests_limit
    ) VALUES (
        NEW.id,
        v_period_start,
        v_period_end,
        10000,  -- Free tier token limit
        100     -- Free tier request limit
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Uncomment to enable automatic free subscription on signup:
-- CREATE TRIGGER trigger_create_free_subscription
--     AFTER INSERT ON auth.users
--     FOR EACH ROW
--     EXECUTE FUNCTION create_free_subscription_on_signup();


-- =============================================================================
-- Comments for Documentation
-- =============================================================================

COMMENT ON TABLE customers IS 'Links Supabase auth users to Stripe customer records';
COMMENT ON TABLE subscriptions IS 'Active subscription state synced from Stripe webhooks';
COMMENT ON TABLE usage_records IS 'Monthly token and request usage per user';
COMMENT ON TABLE billing_events IS 'Audit log of all Stripe webhook events received';
COMMENT ON TABLE invoices IS 'Invoice history cache from Stripe';
COMMENT ON TABLE tier_limits IS 'Subscription tier configuration with limits and features';

COMMENT ON FUNCTION get_tier_limits IS 'Returns quota and features for a subscription tier';
COMMENT ON FUNCTION get_user_subscription IS 'Returns user active subscription with tier limits';
COMMENT ON FUNCTION get_or_create_usage_record IS 'Gets or creates usage record for current billing period';
COMMENT ON FUNCTION increment_usage IS 'Atomically increments token usage and returns quota status';
COMMENT ON FUNCTION check_quota IS 'Checks if user has remaining quota for current period';
COMMENT ON FUNCTION get_billing_summary IS 'Returns comprehensive billing summary for a user';
