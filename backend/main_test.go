package main

import (
	"context"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
)

func TestMigrationPathsOrdersSQLFiles(t *testing.T) {
	dir := t.TempDir()
	for _, name := range []string{"010_later.sql", "001_initial.sql", "README.md"} {
		if err := os.WriteFile(filepath.Join(dir, name), []byte("-- test"), 0o600); err != nil {
			t.Fatal(err)
		}
	}
	paths, err := migrationPaths(dir)
	if err != nil {
		t.Fatal(err)
	}
	want := []string{filepath.Join(dir, "001_initial.sql"), filepath.Join(dir, "010_later.sql")}
	if !reflect.DeepEqual(paths, want) {
		t.Fatalf("migration paths = %v, want %v", paths, want)
	}
}

func TestWorkerLeaseMigrationDefinesLeaseAndStageGuards(t *testing.T) {
	sqlBytes, err := os.ReadFile("migrations/002_worker_leases.sql")
	if err != nil {
		t.Fatal(err)
	}
	contents := string(sqlBytes)
	for _, expected := range []string{
		"lease_owner text",
		"lease_expires_at timestamptz",
		"processing_jobs_stage_check",
		"processing_jobs_claim_eligibility_idx",
	} {
		if !strings.Contains(contents, expected) {
			t.Fatalf("worker lease migration does not contain %q", expected)
		}
	}
}

func TestPhaseEvaluationMigrationMigratesLegacyDebugAndDefinesReviewRoles(t *testing.T) {
	sqlBytes, err := os.ReadFile("migrations/003_phase_evaluation.sql")
	if err != nil {
		t.Fatal(err)
	}
	contents := string(sqlBytes)
	for _, expected := range []string{
		"SET kind = 'debug_telemetry'", "DROP CONSTRAINT IF EXISTS job_artifacts_kind_check",
		"'debug_manifest'", "'debug_measurement'", "'debug_pose'", "'debug_tracking'", "'debug_planning'", "'debug_render'",
	} {
		if !strings.Contains(contents, expected) {
			t.Fatalf("phase evaluation migration does not contain %q", expected)
		}
	}
}

func TestPhaseEvaluationMigrationPostgresBehavior(t *testing.T) {
	databaseURL := os.Getenv("DATABASE_URL")
	if databaseURL == "" {
		t.Skip("DATABASE_URL is not configured; run against a disposable PostgreSQL database to verify migration behavior")
	}
	ctx := context.Background()
	conn, err := pgx.Connect(ctx, databaseURL)
	if err != nil {
		t.Fatal(err)
	}
	defer conn.Close(ctx)
	schema := "phase_evaluation_test_" + strings.ReplaceAll(uuid.NewString(), "-", "")
	if _, err := conn.Exec(ctx, "CREATE SCHEMA "+pgx.Identifier{schema}.Sanitize()); err != nil {
		t.Fatal(err)
	}
	defer func() { _, _ = conn.Exec(ctx, "DROP SCHEMA "+pgx.Identifier{schema}.Sanitize()+" CASCADE") }()
	if _, err := conn.Exec(ctx, "SET search_path TO "+pgx.Identifier{schema}.Sanitize()); err != nil {
		t.Fatal(err)
	}
	for _, name := range []string{"001_init.sql", "002_worker_leases.sql"} {
		sqlBytes, err := os.ReadFile(filepath.Join("migrations", name))
		if err != nil {
			t.Fatal(err)
		}
		if _, err := conn.Exec(ctx, string(sqlBytes)); err != nil {
			t.Fatalf("apply %s: %v", name, err)
		}
	}
	projectID, assetID, jobID, artifactID := uuid.New(), uuid.New(), uuid.New(), uuid.New()
	if _, err := conn.Exec(ctx, `INSERT INTO projects (id,name,owner_id) VALUES ($1,'test','development-owner')`, projectID); err != nil {
		t.Fatal(err)
	}
	if _, err := conn.Exec(ctx, `INSERT INTO assets (id,project_id,kind,storage_key,upload_state) VALUES ($1,$2,'debug',$3,'uploaded')`, assetID, projectID, "private/debug/legacy"); err != nil {
		t.Fatal(err)
	}
	if _, err := conn.Exec(ctx, `INSERT INTO processing_jobs (id,project_id,source_asset_id,state,stage,progress,configuration,configuration_hash) VALUES ($1,$2,$3,'completed','completed',100,'{}',$4)`, jobID, projectID, assetID, jobID.String()); err != nil {
		t.Fatal(err)
	}
	if _, err := conn.Exec(ctx, `INSERT INTO job_artifacts (id,job_id,asset_id,kind) VALUES ($1,$2,$3,'debug')`, artifactID, jobID, assetID); err != nil {
		t.Fatal(err)
	}
	sqlBytes, err := os.ReadFile("migrations/003_phase_evaluation.sql")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := conn.Exec(ctx, string(sqlBytes)); err != nil {
		t.Fatal(err)
	}
	var kind string
	if err := conn.QueryRow(ctx, `SELECT kind FROM job_artifacts WHERE id=$1`, artifactID).Scan(&kind); err != nil || kind != "debug_telemetry" {
		t.Fatalf("legacy artifact kind = %q, %v", kind, err)
	}
	if _, err := conn.Exec(ctx, `INSERT INTO job_artifacts (id,job_id,asset_id,kind) VALUES ($1,$2,$3,'debug_manifest')`, uuid.New(), jobID, assetID); err != nil {
		t.Fatalf("debug_manifest should be accepted: %v", err)
	}
	if _, err := conn.Exec(ctx, `INSERT INTO job_artifacts (id,job_id,asset_id,kind) VALUES ($1,$2,$3,'debug')`, uuid.New(), jobID, assetID); err == nil {
		t.Fatal("legacy debug role was accepted after migration")
	}
	if _, err := conn.Exec(ctx, `INSERT INTO job_artifacts (id,job_id,asset_id,kind) VALUES ($1,$2,$3,'debug_manifest')`, uuid.New(), jobID, assetID); err == nil {
		t.Fatal("duplicate review role was accepted after migration")
	}
}
