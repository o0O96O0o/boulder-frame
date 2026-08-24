DROP CONSTRAINT IF EXISTS job_artifacts_kind_check;

-- Retire only database links for obsolete review roles. Their debug objects may be
-- shared or otherwise retained outside this table, so object-storage lifecycle
-- policy, not this migration, owns their eventual deletion.
ALTER TABLE job_artifacts
  DROP CONSTRAINT IF EXISTS job_artifacts_kind_check;

DELETE FROM job_artifacts
WHERE kind IN (
  'debug_measurement',
  'debug_pose',
  'debug_tracking',
  'debug_planning'
);

ALTER TABLE job_artifacts
  ADD CONSTRAINT job_artifacts_kind_check
  CHECK (kind IN (
    'output',
    'debug_telemetry',
    'debug_manifest',
    'debug_detection',
    'debug_framing',
    'debug_render'
  ));
