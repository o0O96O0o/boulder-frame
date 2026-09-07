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

func TestLoadNormalizesLocalEnvUnconfiguredModelSentinel(t *testing.T) {
	path := writeConfig(t, `{"database_url":"postgres://localhost/db","redis_url":"redis://localhost:6379","s3_endpoint":"http://localhost:9000","s3_presign_endpoint":"http://localhost:9000","s3_region":"us-east-1","s3_bucket":"boulder-frame","s3_access_key":"key","s3_secret_key":"secret","signed_url_ttl":"2m","max_upload_bytes":1234,"model_version":"unset-until-pinned"}`)
	c, err := Load(path)
	if err != nil {
		t.Fatal(err)
	}
	if c.ModelVersion != "unconfigured" {
		t.Fatalf("ModelVersion = %q, want unconfigured", c.ModelVersion)
	}
}

func TestLoadDetectionSampleFPS(t *testing.T) {
	base := `{"database_url":"postgres://localhost/db","redis_url":"redis://localhost:6379","s3_endpoint":"http://localhost:9000","s3_access_key":"key","s3_secret_key":"secret","signed_url_ttl":"2m","max_upload_bytes":1234`
	cases := []struct {
		name    string
		field   string
		want    float64
		wantErr bool
	}{
		{"absent defaults to ten", "", 10, false},
		{"zero means every frame", `,"detection_sample_fps":0`, 0, false},
		{"fractional rate", `,"detection_sample_fps":12.5`, 12.5, false},
		{"upper boundary", `,"detection_sample_fps":1000`, 1000, false},
		{"negative rate", `,"detection_sample_fps":-1`, 0, true},
		{"over upper boundary", `,"detection_sample_fps":1000.01`, 0, true},
		{"not a number", `,"detection_sample_fps":"NaN"`, 0, true},
		{"infinity", `,"detection_sample_fps":"Infinity"`, 0, true},
		{"overflow", `,"detection_sample_fps":1e999`, 0, true},
		{"null", `,"detection_sample_fps":null`, 0, true},
		{"boolean", `,"detection_sample_fps":true`, 0, true},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			cfg, err := Load(writeConfig(t, base+tc.field+"}"))
			if (err != nil) != tc.wantErr {
				t.Fatalf("Load() error = %v, wantErr %v", err, tc.wantErr)
			}
			if err == nil && cfg.DetectionSampleFPS != tc.want {
				t.Fatalf("detection sample rate = %v, want %v", cfg.DetectionSampleFPS, tc.want)
			}
		})
	}
}

func TestLoadDetectionSampleFPSEnvironment(t *testing.T) {
	template := `{"database_url":"postgres://localhost/db","redis_url":"redis://localhost:6379","s3_endpoint":"http://localhost:9000","s3_access_key":"key","s3_secret_key":"secret","signed_url_ttl":"2m","max_upload_bytes":1234,"detection_sample_fps":"${DETECTION_SAMPLE_FPS}"}`
	cases := []struct {
		name    string
		value   string
		want    float64
		wantErr bool
	}{
		{"missing env", "", 10, false},
		{"every frame", "0", 0, false},
		{"fractional env", "7.5", 7.5, false},
		{"invalid env", "not-a-rate", 0, true},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Setenv("DETECTION_SAMPLE_FPS", tc.value)
			if tc.value == "" {
				if err := os.Unsetenv("DETECTION_SAMPLE_FPS"); err != nil {
					t.Fatal(err)
				}
			}
			cfg, err := Load(writeConfig(t, template))
			if (err != nil) != tc.wantErr {
				t.Fatalf("Load() error = %v, wantErr %v", err, tc.wantErr)
			}
			if err == nil && cfg.DetectionSampleFPS != tc.want {
				t.Fatalf("detection sample rate = %v, want %v", cfg.DetectionSampleFPS, tc.want)
			}
		})
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
