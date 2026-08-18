package config

import (
	"os"
	"path/filepath"
	"testing"
)

func TestLoadRejectsMissingDependencies(t *testing.T) {
	path := writeConfig(t, `{"signed_url_ttl":"15m","max_upload_bytes":1}`)
	if _, err := Load(path); err == nil {
		t.Fatal("expected missing configuration error")
	}
}

func TestLoadParsesOverrides(t *testing.T) {
	path := writeConfig(t, `{"http_addr":":9090","database_url":"postgres://localhost/db","redis_url":"redis://localhost:6379","s3_endpoint":"http://localhost:9000","s3_presign_endpoint":"http://localhost:9000","s3_region":"us-east-1","s3_bucket":"boulder-frame","s3_access_key":"key","s3_secret_key":"secret","s3_use_path_style":false,"signed_url_ttl":"2m","max_upload_bytes":1234,"pipeline_version":"test","model_version":"test","development_owner":"test"}`)
	c, err := Load(path)
	if err != nil {
		t.Fatal(err)
	}
	if c.HTTPAddr != ":9090" || c.URLTTL.String() != "2m0s" || c.MaxUploadBytes != 1234 || c.S3UsePathStyle {
		t.Fatalf("unexpected overrides: %+v", c)
	}
}

func writeConfig(t *testing.T, contents string) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "config.json")
	if err := os.WriteFile(path, []byte(contents), 0o600); err != nil {
		t.Fatal(err)
	}
	return path
}
