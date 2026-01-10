-- Subscriptions Table for Stripe Billing Integration
-- Tracks user subscription state synced from Stripe webhooks

CREATE TABLE IF NOT EXISTS subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT UNIQUE,
    plan_id TEXT NOT NULL DEFAULT 'free',
    api_calls_limit INTEGER NOT NULL DEFAULT 100,
    api_calls_used INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'past_due', 'cancelled', 'trialing', 'incomplete')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable Row Level Security
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

-- Users can only view their own subscription
CREATE POLICY "subscriptions_select_own" ON subscriptions
    FOR SELECT USING (auth.uid() = user_id);

-- Service role can do everything (for webhook updates)
CREATE POLICY "subscriptions_service_all" ON subscriptions
    FOR ALL USING (auth.role() = 'service_role');

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_stripe_id ON subscriptions(stripe_subscription_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_subscriptions_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER subscriptions_updated_at
    BEFORE UPDATE ON subscriptions
    FOR EACH ROW
    EXECUTE FUNCTION update_subscriptions_updated_at();

-- Comments
COMMENT ON TABLE subscriptions IS 'User subscription state synced from Stripe webhooks';
COMMENT ON COLUMN subscriptions.plan_id IS 'Plan identifier: free, starter, pro, enterprise';
COMMENT ON COLUMN subscriptions.api_calls_limit IS 'Monthly API call limit for this plan';
COMMENT ON COLUMN subscriptions.api_calls_used IS 'API calls used in current billing period';
COMMENT ON COLUMN subscriptions.status IS 'Subscription status: active, past_due, cancelled, trialing, incomplete';
