ALTER TABLE job_artifacts
  DROP CONSTRAINT IF EXISTS job_artifacts_kind_check;

UPDATE job_artifacts
SET kind = 'debug_telemetry'
WHERE kind = 'debug';

ALTER TABLE job_artifacts
  ADD CONSTRAINT job_artifacts_kind_check
  CHECK (kind IN (
    'output',
    'debug_telemetry',
    'debug_manifest',
    'debug_measurement',
    'debug_pose',
    'debug_tracking',
    'debug_planning',
    'debug_render'
  ));
