-- Add progress column to workers table for real-time progress tracking
-- Migration: 010
-- Description: Add progress JSONB column to workers table to store real-time progress for each phase

-- Add progress column
ALTER TABLE workers ADD COLUMN IF NOT EXISTS progress JSONB;

-- Add comment explaining the column
COMMENT ON COLUMN workers.progress IS 'Real-time progress tracking for each phase: {phase_name: {current: int, total: int, status: str, updated_at: float}}';

-- Example progress structure:
-- {
--   "ingest": {"current": 50, "total": 100, "status": "running", "updated_at": 1704470400.0},
--   "enrich": {"current": 25, "total": 75, "status": "running", "updated_at": 1704470405.0}
-- }

-- Create index for faster queries on progress status
CREATE INDEX IF NOT EXISTS workers_progress_idx ON workers USING GIN (progress);
