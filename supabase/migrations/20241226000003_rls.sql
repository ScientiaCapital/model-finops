-- ============================================================================
-- SUPABASE SETUP - PART 2: Schema Extensions and RLS (Run AFTER Part 1)
-- ============================================================================
-- Run this AFTER running supabase_create_tables.sql
-- URL: https://supabase.com/dashboard/project/nhjhzzkcqtsmfgvairos/sql
-- ============================================================================

-- ============================================================================
-- Add user_id columns for multi-tenancy
-- ============================================================================

-- Add user_id to requests table
ALTER TABLE requests ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id);

-- Add user_id to response_cache table
ALTER TABLE response_cache ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id);

-- Add user_id to routing_metrics table
ALTER TABLE routing_metrics ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id);

-- Add embedding column to response_cache (384 dimensions for semantic search)
ALTER TABLE response_cache ADD COLUMN IF NOT EXISTS embedding vector(384);

-- ============================================================================
-- Create indexes for performance
-- ============================================================================

-- pgvector index for fast semantic search
CREATE INDEX IF NOT EXISTS response_cache_embedding_idx
ON response_cache USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Indexes on user_id for fast user-scoped queries
CREATE INDEX IF NOT EXISTS requests_user_id_idx ON requests(user_id);
CREATE INDEX IF NOT EXISTS response_cache_user_id_idx ON response_cache(user_id);
CREATE INDEX IF NOT EXISTS routing_metrics_user_id_idx ON routing_metrics(user_id);

-- ============================================================================
-- Enable Row-Level Security (RLS)
-- ============================================================================

ALTER TABLE requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE response_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE routing_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE value_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE experiments ENABLE ROW LEVEL SECURITY;
ALTER TABLE experiment_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE routing_feedback ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- Create RLS Policies
-- ============================================================================

-- Drop existing policies if they exist (idempotent)
DROP POLICY IF EXISTS "Users can view own requests" ON requests;
DROP POLICY IF EXISTS "Users can insert own requests" ON requests;
DROP POLICY IF EXISTS "Service role full access requests" ON requests;

DROP POLICY IF EXISTS "Users can view own cache" ON response_cache;
DROP POLICY IF EXISTS "Users can insert own cache" ON response_cache;
DROP POLICY IF EXISTS "Users can update own cache" ON response_cache;
DROP POLICY IF EXISTS "Service role full access cache" ON response_cache;

DROP POLICY IF EXISTS "Users can view own metrics" ON routing_metrics;
DROP POLICY IF EXISTS "Users can insert own metrics" ON routing_metrics;
DROP POLICY IF EXISTS "Service role full access metrics" ON routing_metrics;

DROP POLICY IF EXISTS "Users can view own value metrics" ON value_metrics;
DROP POLICY IF EXISTS "Users can insert own value metrics" ON value_metrics;

DROP POLICY IF EXISTS "Users can view own experiments" ON experiments;
DROP POLICY IF EXISTS "Users can insert own experiments" ON experiments;

DROP POLICY IF EXISTS "Users can view own experiment results" ON experiment_results;
DROP POLICY IF EXISTS "Users can insert own experiment results" ON experiment_results;

DROP POLICY IF EXISTS "Users can view own feedback" ON routing_feedback;
DROP POLICY IF EXISTS "Users can insert own feedback" ON routing_feedback;

-- ============================================================================
-- requests table policies
-- ============================================================================
CREATE POLICY "Users can view own requests"
ON requests FOR SELECT
USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own requests"
ON requests FOR INSERT
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Service role full access requests"
ON requests FOR ALL
USING (auth.jwt() ->> 'role' = 'service_role');

-- ============================================================================
-- response_cache table policies
-- ============================================================================
CREATE POLICY "Users can view own cache"
ON response_cache FOR SELECT
USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own cache"
ON response_cache FOR INSERT
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own cache"
ON response_cache FOR UPDATE
USING (auth.uid() = user_id);

CREATE POLICY "Service role full access cache"
ON response_cache FOR ALL
USING (auth.jwt() ->> 'role' = 'service_role');

-- ============================================================================
-- routing_metrics table policies
-- ============================================================================
CREATE POLICY "Users can view own metrics"
ON routing_metrics FOR SELECT
USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own metrics"
ON routing_metrics FOR INSERT
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Service role full access metrics"
ON routing_metrics FOR ALL
USING (auth.jwt() ->> 'role' = 'service_role');

-- ============================================================================
-- value_metrics table policies
-- ============================================================================
CREATE POLICY "Users can view own value metrics"
ON value_metrics FOR SELECT
USING (auth.uid() = user_id::uuid);

CREATE POLICY "Users can insert own value metrics"
ON value_metrics FOR INSERT
WITH CHECK (auth.uid() = user_id::uuid);

-- ============================================================================
-- experiments table policies
-- ============================================================================
CREATE POLICY "Users can view own experiments"
ON experiments FOR SELECT
USING (auth.uid()::text = created_by);

CREATE POLICY "Users can insert own experiments"
ON experiments FOR INSERT
WITH CHECK (auth.uid()::text = created_by);

-- ============================================================================
-- experiment_results table policies
-- ============================================================================
CREATE POLICY "Users can view own experiment results"
ON experiment_results FOR SELECT
USING (auth.uid()::text = user_id);

CREATE POLICY "Users can insert own experiment results"
ON experiment_results FOR INSERT
WITH CHECK (auth.uid()::text = user_id);

-- ============================================================================
-- routing_feedback table policies
-- ============================================================================
CREATE POLICY "Users can view own feedback"
ON routing_feedback FOR SELECT
USING (auth.uid()::text = user_id);

CREATE POLICY "Users can insert own feedback"
ON routing_feedback FOR INSERT
WITH CHECK (auth.uid()::text = user_id);

-- ============================================================================
-- Verification
-- ============================================================================

-- Show RLS status
SELECT
    tablename,
    CASE WHEN rowsecurity THEN '✅ RLS Enabled' ELSE '❌ RLS Disabled' END as status
FROM pg_tables
WHERE schemaname = 'public'
    AND tablename IN ('requests', 'response_cache', 'routing_metrics',
                      'value_metrics', 'experiments', 'experiment_results', 'routing_feedback')
ORDER BY tablename;

-- Show created indexes
SELECT
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
    AND (indexname LIKE '%user_id%' OR indexname LIKE '%embedding%')
ORDER BY tablename, indexname;

-- Success message
SELECT '✅ PART 2 COMPLETE - Schema and RLS configured!' as status;
SELECT 'Multi-tenant Supabase setup is now complete!' as message;
