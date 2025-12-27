-- Migration: arbitrage_001_capability_registry
-- Creates tables for provider arbitrage detection system
-- Features: Model capabilities, pricing, arbitrage opportunities

-- ==============================================================================
-- ENUMS
-- ==============================================================================

-- Capability types for AI models
CREATE TYPE model_capability AS ENUM (
    'code_gen',
    'code_review',
    'reasoning',
    'math',
    'creative',
    'analysis',
    'translation',
    'summarization',
    'vision',
    'audio',
    'function_calling',
    'json_mode'
);

-- Capability proficiency levels
CREATE TYPE capability_level AS ENUM (
    'basic',
    'intermediate',
    'advanced',
    'expert'
);

-- ==============================================================================
-- TABLES
-- ==============================================================================

-- Model capabilities registry (extends static code registry)
-- Allows runtime updates to pricing and capabilities
CREATE TABLE model_capabilities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider TEXT NOT NULL,
    model_id TEXT NOT NULL UNIQUE,
    capabilities JSONB NOT NULL DEFAULT '{}',  -- {capability: level}
    input_price_per_million DECIMAL(10, 6) NOT NULL,
    output_price_per_million DECIMAL(10, 6) NOT NULL,
    context_window INTEGER NOT NULL,
    avg_latency_ms INTEGER,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Index for provider lookups
CREATE INDEX idx_model_capabilities_provider ON model_capabilities(provider);

-- Index for active models
CREATE INDEX idx_model_capabilities_active ON model_capabilities(is_active) WHERE is_active = true;

-- GIN index for capability queries
CREATE INDEX idx_model_capabilities_caps ON model_capabilities USING GIN (capabilities);

-- Arbitrage opportunities log
-- Tracks when cheaper alternatives were identified
CREATE TABLE arbitrage_opportunities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    request_id UUID,  -- Optional reference to original request
    current_model TEXT NOT NULL,
    alternative_model TEXT NOT NULL,
    current_cost DECIMAL(10, 6) NOT NULL,
    alternative_cost DECIMAL(10, 6) NOT NULL,
    savings_percent DECIMAL(5, 2) NOT NULL,
    required_capabilities TEXT[] NOT NULL,
    was_applied BOOLEAN DEFAULT false,
    quality_validated BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Index for user lookups
CREATE INDEX idx_arbitrage_opportunities_user ON arbitrage_opportunities(user_id);

-- Index for time-based queries
CREATE INDEX idx_arbitrage_opportunities_created ON arbitrage_opportunities(created_at DESC);

-- Index for applied opportunities
CREATE INDEX idx_arbitrage_opportunities_applied ON arbitrage_opportunities(was_applied, user_id);

-- Quality benchmarks learned from history
-- Tracks model performance for specific task types
CREATE TABLE model_quality_benchmarks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id TEXT NOT NULL,
    task_type TEXT NOT NULL,
    capability model_capability NOT NULL,
    avg_quality_score DECIMAL(5, 4) NOT NULL,  -- 0.0000 to 1.0000
    sample_count INTEGER DEFAULT 0,
    confidence DECIMAL(5, 4) DEFAULT 0,  -- Wilson score
    user_rating_avg DECIMAL(3, 2),  -- Optional user ratings
    last_updated TIMESTAMPTZ DEFAULT now(),
    UNIQUE (model_id, task_type, capability)
);

-- Index for model lookups
CREATE INDEX idx_model_quality_benchmarks_model ON model_quality_benchmarks(model_id);

-- Index for capability queries
CREATE INDEX idx_model_quality_benchmarks_cap ON model_quality_benchmarks(capability);

-- ==============================================================================
-- ROW LEVEL SECURITY
-- ==============================================================================

-- Enable RLS
ALTER TABLE model_capabilities ENABLE ROW LEVEL SECURITY;
ALTER TABLE arbitrage_opportunities ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_quality_benchmarks ENABLE ROW LEVEL SECURITY;

-- model_capabilities: Read-only for all authenticated users
CREATE POLICY "model_capabilities_select" ON model_capabilities
    FOR SELECT TO authenticated USING (true);

-- model_capabilities: Admin-only insert/update (using service role)
CREATE POLICY "model_capabilities_service" ON model_capabilities
    FOR ALL TO service_role USING (true);

-- arbitrage_opportunities: Users see only their own
CREATE POLICY "arbitrage_opportunities_select" ON arbitrage_opportunities
    FOR SELECT TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "arbitrage_opportunities_insert" ON arbitrage_opportunities
    FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "arbitrage_opportunities_update" ON arbitrage_opportunities
    FOR UPDATE TO authenticated
    USING (auth.uid() = user_id);

-- model_quality_benchmarks: Read-only for all (aggregated data)
CREATE POLICY "model_quality_benchmarks_select" ON model_quality_benchmarks
    FOR SELECT TO authenticated USING (true);

-- model_quality_benchmarks: Service role can update
CREATE POLICY "model_quality_benchmarks_service" ON model_quality_benchmarks
    FOR ALL TO service_role USING (true);

-- ==============================================================================
-- FUNCTIONS
-- ==============================================================================

-- Function to update timestamps
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for model_capabilities
CREATE TRIGGER update_model_capabilities_modtime
    BEFORE UPDATE ON model_capabilities
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();

-- Function to calculate arbitrage savings
CREATE OR REPLACE FUNCTION calculate_arbitrage_savings(
    current_input_price DECIMAL,
    current_output_price DECIMAL,
    alt_input_price DECIMAL,
    alt_output_price DECIMAL,
    input_tokens INTEGER,
    output_tokens INTEGER
) RETURNS DECIMAL AS $$
DECLARE
    current_cost DECIMAL;
    alt_cost DECIMAL;
BEGIN
    current_cost := (input_tokens / 1000000.0) * current_input_price +
                    (output_tokens / 1000000.0) * current_output_price;
    alt_cost := (input_tokens / 1000000.0) * alt_input_price +
                (output_tokens / 1000000.0) * alt_output_price;

    IF current_cost = 0 THEN
        RETURN 0;
    END IF;

    RETURN ((current_cost - alt_cost) / current_cost) * 100;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ==============================================================================
-- SEED DATA: Initial model capabilities
-- ==============================================================================

INSERT INTO model_capabilities (provider, model_id, capabilities, input_price_per_million, output_price_per_million, context_window, avg_latency_ms) VALUES
-- Gemini Models
('gemini', 'gemini-1.5-flash',
 '{"code_gen": "intermediate", "reasoning": "intermediate", "creative": "intermediate", "analysis": "intermediate", "summarization": "advanced", "math": "intermediate", "vision": "intermediate", "json_mode": "advanced"}'::jsonb,
 0.075, 0.30, 1000000, 400),

('gemini', 'gemini-1.5-pro',
 '{"code_gen": "advanced", "reasoning": "advanced", "creative": "advanced", "analysis": "advanced", "summarization": "advanced", "math": "advanced", "vision": "advanced", "json_mode": "advanced"}'::jsonb,
 1.25, 5.00, 2000000, 600),

-- Anthropic Models
('anthropic', 'claude-3-5-sonnet-20241022',
 '{"code_gen": "expert", "code_review": "expert", "reasoning": "expert", "creative": "expert", "analysis": "expert", "summarization": "expert", "math": "advanced", "vision": "advanced", "json_mode": "expert", "function_calling": "expert"}'::jsonb,
 3.00, 15.00, 200000, 800),

('anthropic', 'claude-3-5-haiku-20241022',
 '{"code_gen": "intermediate", "reasoning": "intermediate", "creative": "intermediate", "analysis": "intermediate", "summarization": "advanced", "json_mode": "advanced", "function_calling": "intermediate"}'::jsonb,
 0.80, 4.00, 200000, 300),

-- Groq Models
('groq', 'llama-3.3-70b-versatile',
 '{"code_gen": "advanced", "reasoning": "advanced", "creative": "intermediate", "analysis": "advanced", "summarization": "advanced", "math": "intermediate", "json_mode": "intermediate"}'::jsonb,
 0.59, 0.79, 128000, 150),

('groq', 'llama-3.1-8b-instant',
 '{"code_gen": "basic", "reasoning": "basic", "creative": "basic", "summarization": "intermediate", "json_mode": "basic"}'::jsonb,
 0.05, 0.08, 128000, 80),

-- Cerebras Models
('cerebras', 'llama3.1-70b',
 '{"code_gen": "advanced", "reasoning": "advanced", "creative": "intermediate", "analysis": "advanced", "math": "intermediate"}'::jsonb,
 0.60, 0.60, 128000, 100),

-- DeepSeek Models
('deepseek', 'deepseek-chat',
 '{"code_gen": "advanced", "reasoning": "advanced", "analysis": "advanced", "math": "advanced", "json_mode": "intermediate"}'::jsonb,
 0.14, 0.28, 64000, 500),

('deepseek', 'deepseek-coder',
 '{"code_gen": "expert", "code_review": "advanced", "reasoning": "intermediate"}'::jsonb,
 0.14, 0.28, 64000, 450);

COMMENT ON TABLE model_capabilities IS 'Registry of AI model capabilities and pricing for arbitrage detection';
COMMENT ON TABLE arbitrage_opportunities IS 'Log of identified cost-saving opportunities through model switching';
COMMENT ON TABLE model_quality_benchmarks IS 'Learned quality scores for models on specific task types';
