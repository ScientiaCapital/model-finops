-- ============================================================================
-- SUPABASE SETUP - PART 1: Extensions and Functions (Run NOW)
-- ============================================================================
-- Run this BEFORE Alembic migrations
-- URL: https://supabase.com/dashboard/project/nhjhzzkcqtsmfgvairos/sql
-- ============================================================================

-- Enable pgvector for semantic search with embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable pg_trgm for text similarity and fuzzy matching
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Enable uuid-ossp for UUID generation functions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- Verify extensions are enabled
-- ============================================================================
SELECT
    extname AS extension_name,
    extversion AS version,
    CASE
        WHEN extname = 'vector' THEN '✅ Semantic search enabled'
        WHEN extname = 'pg_trgm' THEN '✅ Text similarity enabled'
        WHEN extname = 'uuid-ossp' THEN '✅ UUID generation enabled'
        ELSE 'Other extension'
    END AS status
FROM pg_extension
WHERE extname IN ('vector', 'pg_trgm', 'uuid-ossp')
ORDER BY extname;

-- ============================================================================
-- Create pgvector semantic search function (can create before tables exist)
-- ============================================================================
CREATE OR REPLACE FUNCTION match_cache_entries(
    query_embedding vector(384),
    match_threshold float DEFAULT 0.95,
    match_count int DEFAULT 1,
    target_user_id uuid DEFAULT NULL
)
RETURNS TABLE (
    cache_key text,
    prompt_normalized text,
    response text,
    provider text,
    model text,
    similarity float,
    hit_count int,
    quality_score float
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT
        rc.cache_key,
        rc.prompt_normalized,
        rc.response,
        rc.provider,
        rc.model,
        (1 - (rc.embedding <=> query_embedding))::float as similarity,
        rc.hit_count,
        rc.quality_score
    FROM response_cache rc
    WHERE
        (rc.invalidated IS NULL OR rc.invalidated = 0)
        AND (target_user_id IS NULL OR rc.user_id = target_user_id)
        AND (1 - (rc.embedding <=> query_embedding)) > match_threshold
    ORDER BY
        rc.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Grant execute permission
GRANT EXECUTE ON FUNCTION match_cache_entries TO authenticated;
GRANT EXECUTE ON FUNCTION match_cache_entries TO service_role;

-- ============================================================================
-- Create helper function for user cache stats
-- ============================================================================
CREATE OR REPLACE FUNCTION get_user_cache_stats(target_user_id uuid)
RETURNS TABLE (
    total_entries bigint,
    total_hits bigint,
    avg_quality_score float,
    cache_size_bytes bigint
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::bigint as total_entries,
        COALESCE(SUM(hit_count), 0)::bigint as total_hits,
        COALESCE(AVG(quality_score), 0.0)::float as avg_quality_score,
        COALESCE(SUM(LENGTH(response)), 0)::bigint as cache_size_bytes
    FROM response_cache
    WHERE user_id = target_user_id
        AND (invalidated IS NULL OR invalidated = 0);
END;
$$;

GRANT EXECUTE ON FUNCTION get_user_cache_stats TO authenticated;
GRANT EXECUTE ON FUNCTION get_user_cache_stats TO service_role;

-- ============================================================================
-- Success!
-- ============================================================================
SELECT '✅ PART 1 COMPLETE - Extensions and functions created!' as status;
SELECT 'Next: Run Alembic migrations, then run supabase_part2_schema.sql' as next_step;
