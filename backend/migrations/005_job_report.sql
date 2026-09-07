ALTER TABLE processing_jobs
  ADD COLUMN IF NOT EXISTS report jsonb;
