-- Additive columns for external telemetry ingestion (POST /api/telemetry/ingest).
-- Safe to run multiple times; existing rows get NULL for these columns.
-- Run in the Supabase SQL Editor: https://supabase.com/dashboard/project/YOUR_PROJECT/sql

ALTER TABLE requests ADD COLUMN IF NOT EXISTS project_id TEXT;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS session_id TEXT;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS task_type TEXT;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS latency_ms INTEGER;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'model-finops';
