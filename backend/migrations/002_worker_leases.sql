ALTER TABLE processing_jobs
  ADD COLUMN IF NOT EXISTS lease_owner text,
  ADD COLUMN IF NOT EXISTS lease_expires_at timestamptz;

DO $$
BEGIN
  ALTER TABLE processing_jobs
    ADD CONSTRAINT processing_jobs_stage_check
    CHECK (stage IN ('queued','validating','analyzing','rendering','uploading','completed','failed','cancelled'));
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS processing_jobs_claim_eligibility_idx
  ON processing_jobs (id, lease_expires_at)
  WHERE state NOT IN ('completed', 'failed', 'cancelled');
