CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS development_owners (id text PRIMARY KEY, created_at timestamptz NOT NULL DEFAULT now());
INSERT INTO development_owners (id) VALUES ('development-owner') ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS projects (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name text NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 200),
  owner_id text NOT NULL REFERENCES development_owners(id), created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS assets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  kind text NOT NULL CHECK (kind IN ('source','output','debug')), storage_key text NOT NULL UNIQUE,
  upload_state text NOT NULL CHECK (upload_state IN ('pending','uploaded','invalid')), filename text,
  content_type text, size_bytes bigint NOT NULL DEFAULT 0 CHECK (size_bytes >= 0), width integer, height integer,
  frame_rate double precision, duration_ms bigint, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS processing_jobs (
  id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  source_asset_id uuid NOT NULL REFERENCES assets(id), state text NOT NULL CHECK (state IN ('queued','validating','analyzing','rendering','uploading','completed','failed','cancelled')),
  stage text NOT NULL, progress integer NOT NULL CHECK (progress BETWEEN 0 AND 100), configuration jsonb NOT NULL,
  configuration_hash text NOT NULL, error_code text, error_message text, output_asset_id uuid REFERENCES assets(id),
  created_at timestamptz NOT NULL DEFAULT now(), started_at timestamptz, completed_at timestamptz,
  UNIQUE (project_id, configuration_hash)
);
CREATE TABLE IF NOT EXISTS job_artifacts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), job_id uuid NOT NULL REFERENCES processing_jobs(id) ON DELETE CASCADE,
  asset_id uuid NOT NULL REFERENCES assets(id), kind text NOT NULL CHECK (kind IN ('output','debug')),
  created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(job_id, kind)
);
