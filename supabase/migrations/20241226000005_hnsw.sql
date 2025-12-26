-- ============================================================================
-- UPGRADE: IVFFlat to HNSW Index for Better Semantic Search Performance
-- ============================================================================
-- This migration upgrades the vector index from IVFFlat to HNSW.
--
-- HNSW (Hierarchical Navigable Small World) provides:
-- - Better query performance (especially for smaller datasets)
-- - No need for training/maintenance
-- - More accurate approximate nearest neighbor search
--
-- Trade-offs:
-- - Slower index build time
-- - Higher memory usage (2-3x compared to IVFFlat)
--
-- For semantic caching where reads >> writes, HNSW is the optimal choice.
-- ============================================================================
-- Run in: https://supabase.com/dashboard/project/YOUR_PROJECT/sql
-- ============================================================================

-- Step 1: Drop the existing IVFFlat index
DROP INDEX IF EXISTS response_cache_embedding_idx;

-- Step 2: Create new HNSW index
-- Parameters:
--   m = 16: Number of connections per node (default is 16, higher = more accurate but slower)
--   ef_construction = 64: Size of dynamic candidate list during build (default 64)
--
-- For semantic caching with 384-dimensional embeddings:
--   - m=16 provides good balance of accuracy and speed
--   - ef_construction=64 is sufficient for most use cases
CREATE INDEX response_cache_embedding_hnsw_idx
ON response_cache
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Step 3: Verify the index was created
SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
    AND tablename = 'response_cache'
    AND indexname LIKE '%embedding%';

-- Step 4: Analyze the table to update statistics
ANALYZE response_cache;

-- ============================================================================
-- Optional: Tune HNSW search parameters at runtime
-- ============================================================================
-- You can adjust ef_search (default 40) for individual sessions:
--   SET hnsw.ef_search = 100;  -- Higher = more accurate but slower
--
-- This can be done per-query for critical searches that need higher accuracy.
-- ============================================================================

-- Success message
SELECT '✅ HNSW Index Migration Complete!' as status;
SELECT 'Semantic search should now be faster and more accurate.' as message;
