package main

import (
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
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
