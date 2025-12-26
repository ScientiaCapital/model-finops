-- ============================================================================
-- ENHANCED SEMANTIC SEARCH: Add Metadata Filtering Support
-- ============================================================================
-- This migration adds an enhanced semantic search function that supports:
-- - Provider filtering (only match responses from specific providers)
-- - Model filtering (only match responses from specific models)
-- - Minimum quality score filtering
-- - Maximum age filtering (exclude stale cache entries)
--
-- Use case: "Find similar prompts, but only from Claude responses with quality > 0.7"
-- ============================================================================
-- Run in: https://supabase.com/dashboard/project/YOUR_PROJECT/sql
-- ============================================================================

-- Create enhanced semantic search function with metadata filtering
CREATE OR REPLACE FUNCTION match_cache_entries_v2(
    query_embedding vector(384),
    match_threshold float DEFAULT 0.95,
    match_count int DEFAULT 1,
    target_user_id uuid DEFAULT NULL,
    -- NEW: Metadata filters
    filter_providers text[] DEFAULT NULL,      -- e.g., ARRAY['claude', 'gemini']
    filter_models text[] DEFAULT NULL,         -- e.g., ARRAY['claude-3-haiku', 'gemini-flash']
    min_quality_score float DEFAULT NULL,      -- e.g., 0.7
    max_age_hours int DEFAULT NULL             -- e.g., 24 (only last 24 hours)
)
RETURNS TABLE (
    cache_key text,
    prompt_normalized text,
    response text,
    provider text,
    model text,
    similarity float,
    hit_count int,
    quality_score float,
    created_at text,
    tokens_in int,
    tokens_out int,
    cost float
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
        rc.quality_score,
        rc.created_at,
        rc.tokens_in,
        rc.tokens_out,
        rc.cost
    FROM response_cache rc
    WHERE
        -- Basic filters (existing)
        (rc.invalidated IS NULL OR rc.invalidated = 0)
        AND (target_user_id IS NULL OR rc.user_id = target_user_id)
        AND (1 - (rc.embedding <=> query_embedding)) > match_threshold

        -- NEW: Provider filter
        AND (filter_providers IS NULL OR rc.provider = ANY(filter_providers))

        -- NEW: Model filter
        AND (filter_models IS NULL OR rc.model = ANY(filter_models))

        -- NEW: Quality score filter
        AND (min_quality_score IS NULL OR rc.quality_score >= min_quality_score)

        -- NEW: Age filter (only include entries created within max_age_hours)
        AND (
            max_age_hours IS NULL
            OR rc.created_at::timestamp > NOW() - (max_age_hours || ' hours')::interval
        )
    ORDER BY
        -- Primary sort: similarity (most similar first)
        rc.embedding <=> query_embedding,
        -- Secondary sort: prefer higher quality responses
        rc.quality_score DESC NULLS LAST,
        -- Tertiary sort: prefer more popular (more hits)
        rc.hit_count DESC
    LIMIT match_count;
END;
$$;

-- Grant execute permission
GRANT EXECUTE ON FUNCTION match_cache_entries_v2 TO authenticated;
GRANT EXECUTE ON FUNCTION match_cache_entries_v2 TO service_role;

-- ============================================================================
-- Add helper function to find similar prompts (for cache warming/analysis)
-- ============================================================================
CREATE OR REPLACE FUNCTION find_similar_prompts(
    target_prompt text,
    similarity_threshold float DEFAULT 0.80,
    max_results int DEFAULT 10,
    target_user_id uuid DEFAULT NULL
)
RETURNS TABLE (
    cache_key text,
    prompt_normalized text,
    provider text,
    model text,
    similarity float,
    hit_count int,
    quality_score float
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    query_embedding vector(384);
BEGIN
    -- Note: This function expects the embedding to be generated client-side
    -- and passed to match_cache_entries_v2 directly for production use.
    -- This is a convenience function for analysis/exploration.

    RETURN QUERY
    SELECT
        rc.cache_key,
        rc.prompt_normalized,
        rc.provider,
        rc.model,
        0.0::float as similarity,  -- Placeholder - compute client-side
        rc.hit_count,
        rc.quality_score
    FROM response_cache rc
    WHERE
        (rc.invalidated IS NULL OR rc.invalidated = 0)
        AND (target_user_id IS NULL OR rc.user_id = target_user_id)
        -- Use trigram similarity for text-based search (fallback)
        AND similarity(rc.prompt_normalized, target_prompt) > similarity_threshold
    ORDER BY
        similarity(rc.prompt_normalized, target_prompt) DESC,
        rc.quality_score DESC NULLS LAST
    LIMIT max_results;
END;
$$;

GRANT EXECUTE ON FUNCTION find_similar_prompts TO authenticated;
GRANT EXECUTE ON FUNCTION find_similar_prompts TO service_role;

-- ============================================================================
-- Cache Analytics Functions
-- ============================================================================

-- Get cache hit rate statistics by provider
CREATE OR REPLACE FUNCTION get_cache_analytics(
    target_user_id uuid DEFAULT NULL,
    days_back int DEFAULT 7
)
RETURNS TABLE (
    provider text,
    total_entries bigint,
    total_hits bigint,
    avg_quality float,
    avg_similarity float,
    hit_rate float
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT
        rc.provider,
        COUNT(*)::bigint as total_entries,
        COALESCE(SUM(rc.hit_count), 0)::bigint as total_hits,
        COALESCE(AVG(rc.quality_score), 0.0)::float as avg_quality,
        0.0::float as avg_similarity,  -- Would need join with request logs
        CASE
            WHEN COUNT(*) > 0 THEN
                (COALESCE(SUM(rc.hit_count), 0)::float / COUNT(*)::float)
            ELSE 0.0
        END as hit_rate
    FROM response_cache rc
    WHERE
        (rc.invalidated IS NULL OR rc.invalidated = 0)
        AND (target_user_id IS NULL OR rc.user_id = target_user_id)
        AND (
            days_back IS NULL
            OR rc.created_at::timestamp > NOW() - (days_back || ' days')::interval
        )
    GROUP BY rc.provider
    ORDER BY total_hits DESC;
END;
$$;

GRANT EXECUTE ON FUNCTION get_cache_analytics TO authenticated;
GRANT EXECUTE ON FUNCTION get_cache_analytics TO service_role;

-- ============================================================================
-- Verification
-- ============================================================================

SELECT '✅ Enhanced Semantic Search Functions Created!' as status;

-- List all cache-related functions
SELECT
    routine_name,
    routine_type
FROM information_schema.routines
WHERE routine_schema = 'public'
    AND routine_name LIKE '%cache%'
ORDER BY routine_name;
