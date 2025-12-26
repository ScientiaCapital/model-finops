-- ============================================================================
-- CREATE ALL TABLES - Run this in Supabase SQL Editor
-- ============================================================================
-- This combines all Alembic migrations into one SQL script
-- URL: https://supabase.com/dashboard/project/nhjhzzkcqtsmfgvairos/sql
-- ============================================================================

-- ============================================================================
-- Migration 1: Initial Schema (requests, response_cache, response_feedback)
-- ============================================================================

CREATE TABLE IF NOT EXISTS requests (
    id SERIAL PRIMARY KEY,
    timestamp TEXT NOT NULL,
    prompt_preview TEXT NOT NULL,
    complexity TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    tokens_in INTEGER NOT NULL,
    tokens_out INTEGER NOT NULL,
    cost FLOAT NOT NULL
);

CREATE TABLE IF NOT EXISTS response_cache (
    cache_key TEXT PRIMARY KEY,
    prompt_normalized TEXT NOT NULL,
    max_tokens INTEGER NOT NULL,
    response TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    complexity TEXT NOT NULL,
    tokens_in INTEGER NOT NULL,
    tokens_out INTEGER NOT NULL,
    cost FLOAT NOT NULL,
    created_at TEXT NOT NULL,
    last_accessed TEXT NOT NULL,
    hit_count INTEGER DEFAULT 0,
    upvotes INTEGER DEFAULT 0,
    downvotes INTEGER DEFAULT 0,
    quality_score FLOAT,
    invalidated INTEGER DEFAULT 0,
    invalidation_reason TEXT
);

CREATE TABLE IF NOT EXISTS response_feedback (
    id SERIAL PRIMARY KEY,
    cache_key TEXT NOT NULL,
    rating INTEGER NOT NULL,
    comment TEXT,
    user_agent TEXT,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (cache_key) REFERENCES response_cache(cache_key)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_cache_prompt ON response_cache(prompt_normalized);
CREATE INDEX IF NOT EXISTS idx_cache_created ON response_cache(created_at);
CREATE INDEX IF NOT EXISTS idx_feedback_cache_key ON response_feedback(cache_key);

-- ============================================================================
-- Migration 2: Value Metrics Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS value_metrics (
    id SERIAL PRIMARY KEY,
    user_id TEXT,
    session_id TEXT,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    baseline_cost FLOAT NOT NULL,
    optimized_cost FLOAT NOT NULL,
    savings FLOAT NOT NULL,
    baseline_provider TEXT NOT NULL,
    optimized_provider TEXT NOT NULL,
    prompt_category TEXT,
    model_comparison JSONB
);

CREATE INDEX IF NOT EXISTS idx_value_metrics_user ON value_metrics(user_id);
CREATE INDEX IF NOT EXISTS idx_value_metrics_session ON value_metrics(session_id);
CREATE INDEX IF NOT EXISTS idx_value_metrics_timestamp ON value_metrics(timestamp);

-- ============================================================================
-- Migration 3: Feedback Tables (routing_feedback, model_performance_history)
-- ============================================================================

CREATE TABLE IF NOT EXISTS routing_feedback (
    id SERIAL PRIMARY KEY,
    request_id TEXT UNIQUE NOT NULL,
    user_id TEXT,
    session_id TEXT,
    prompt_pattern TEXT NOT NULL,
    selected_provider TEXT NOT NULL,
    selected_model TEXT NOT NULL,
    quality_score FLOAT CHECK (quality_score >= 0 AND quality_score <= 1),
    is_correct BOOLEAN,
    is_helpful BOOLEAN,
    comment TEXT,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS model_performance_history (
    id SERIAL PRIMARY KEY,
    pattern TEXT NOT NULL,
    model TEXT NOT NULL,
    avg_quality_score FLOAT NOT NULL,
    correctness_rate FLOAT NOT NULL,
    sample_count INTEGER NOT NULL,
    confidence_level TEXT NOT NULL CHECK (confidence_level IN ('high', 'medium', 'low')),
    retraining_run_id TEXT NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(pattern, model, retraining_run_id)
);

CREATE INDEX IF NOT EXISTS idx_routing_feedback_user ON routing_feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_routing_feedback_pattern ON routing_feedback(prompt_pattern);
CREATE INDEX IF NOT EXISTS idx_model_performance_pattern ON model_performance_history(pattern);
CREATE INDEX IF NOT EXISTS idx_model_performance_model ON model_performance_history(model);

-- ============================================================================
-- Migration 4: Routing Metrics Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS routing_metrics (
    id SERIAL PRIMARY KEY,
    request_id TEXT UNIQUE NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    prompt_preview TEXT NOT NULL,
    strategy_used TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    confidence TEXT NOT NULL,
    tokens_in INTEGER NOT NULL,
    tokens_out INTEGER NOT NULL,
    cost FLOAT NOT NULL,
    cache_hit BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_routing_metrics_timestamp ON routing_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_routing_metrics_strategy ON routing_metrics(strategy_used);
CREATE INDEX IF NOT EXISTS idx_routing_metrics_provider ON routing_metrics(provider);
CREATE INDEX IF NOT EXISTS idx_routing_metrics_confidence ON routing_metrics(confidence);

-- ============================================================================
-- Migration 5: Experiments and Results Tables
-- ============================================================================

CREATE TABLE IF NOT EXISTS experiments (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    control_strategy TEXT NOT NULL,
    test_strategy TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'completed')),
    created_by TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS experiment_results (
    id SERIAL PRIMARY KEY,
    experiment_id INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    assigned_strategy TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    latency_ms FLOAT,
    cost_usd FLOAT,
    quality_score FLOAT CHECK (quality_score >= 0 AND quality_score <= 1),
    provider TEXT,
    model TEXT,
    FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_experiments_status ON experiments(status);
CREATE INDEX IF NOT EXISTS idx_experiment_results_experiment ON experiment_results(experiment_id);
CREATE INDEX IF NOT EXISTS idx_experiment_results_user ON experiment_results(user_id);
CREATE INDEX IF NOT EXISTS idx_experiment_results_strategy ON experiment_results(assigned_strategy);

-- ============================================================================
-- Verification
-- ============================================================================

SELECT '✅ ALL TABLES CREATED!' as status;

-- Show created tables
SELECT
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns WHERE columns.table_name = tables.table_name) as column_count
FROM information_schema.tables
WHERE table_schema = 'public'
    AND table_type = 'BASE TABLE'
ORDER BY table_name;

-- Show indexes
SELECT
    schemaname,
    tablename,
    indexname
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;
