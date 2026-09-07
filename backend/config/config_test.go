package config

import (
	"strings"
	"testing"
	"time"
)

func TestLoadRejectsMissingDependencies(t *testing.T) {
	for _, name := range []string{"DATABASE_URL", "REDIS_URL", "S3_ENDPOINT", "S3_ACCESS_KEY", "S3_SECRET_KEY"} {
		t.Run(name, func(t *testing.T) {
			setConfigEnv(t)
			t.Setenv(name, "")
			if _, err := Load(); err == nil || !strings.Contains(err.Error(), name) {
				t.Fatalf("Load() error = %v, want missing %s", err, name)
			}
		})
	}
}

func TestLoadParsesEnvironmentTypes(t *testing.T) {
	setConfigEnv(t)
	t.Setenv("S3_FORCE_PATH_STYLE", "false")
	t.Setenv("SIGNED_URL_TTL", "2m")
	t.Setenv("MAX_UPLOAD_BYTES", "1234")
	c, err := Load()
	if err != nil {
		t.Fatal(err)
	}
	if c.URLTTL != 2*time.Minute || c.MaxUploadBytes != 1234 || c.S3UsePathStyle {
		t.Fatalf("unexpected parsed values: TTL=%v, max upload=%d, path style=%v", c.URLTTL, c.MaxUploadBytes, c.S3UsePathStyle)
	}
}

func TestLoadRejectsMalformedEnvironment(t *testing.T) {
	cases := []struct {
		name  string
		value string
	}{
		{"S3_FORCE_PATH_STYLE", "not-a-bool"},
		{"SIGNED_URL_TTL", "15"},
		{"SIGNED_URL_TTL", "0s"},
		{"SIGNED_URL_TTL", "-1m"},
		{"MAX_UPLOAD_BYTES", "not-an-integer"},
		{"MAX_UPLOAD_BYTES", "1.5"},
		{"MAX_UPLOAD_BYTES", "9223372036854775808"},
		{"MAX_UPLOAD_BYTES", "0"},
		{"MAX_UPLOAD_BYTES", "-1"},
		{"DATABASE_URL", "://invalid"},
		{"REDIS_URL", "redis://%zz"},
		{"S3_ENDPOINT", "localhost"},
	}
	for _, tc := range cases {
		t.Run(tc.name+"/"+tc.value, func(t *testing.T) {
			setConfigEnv(t)
			t.Setenv(tc.name, tc.value)
			if _, err := Load(); err == nil || !strings.Contains(err.Error(), tc.name) {
				t.Fatalf("Load() error = %v, want invalid %s", err, tc.name)
			}
		})
	}
}

func TestLoadNormalizesLocalEnvUnconfiguredModelSentinel(t *testing.T) {
	setConfigEnv(t)
	t.Setenv("MODEL_VERSION", "unset-until-pinned")
	c, err := Load()
	if err != nil {
		t.Fatal(err)
	}
	if c.ModelVersion != "unconfigured" {
		t.Fatalf("ModelVersion = %q, want unconfigured", c.ModelVersion)
	}
}

func TestLoadDetectionSampleFPS(t *testing.T) {
	cases := []struct {
		name    string
		value   string
		want    float64
		wantErr bool
	}{
		{"zero means every frame", "0", 0, false},
		{"fractional rate", "12.5", 12.5, false},
		{"upper boundary", "1000", 1000, false},
		{"negative rate", "-1", 0, true},
		{"over upper boundary", "1000.01", 0, true},
		{"not a number", "NaN", 0, true},
		{"infinity", "Infinity", 0, true},
		{"overflow", "1e999", 0, true},
		{"invalid number", "not-a-rate", 0, true},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			setConfigEnv(t)
			t.Setenv("DETECTION_SAMPLE_FPS", tc.value)
			cfg, err := Load()
			if (err != nil) != tc.wantErr {
				t.Fatalf("Load() error = %v, wantErr %v", err, tc.wantErr)
			}
			if err == nil && cfg.DetectionSampleFPS != tc.want {
				t.Fatalf("detection sample rate = %v, want %v", cfg.DetectionSampleFPS, tc.want)
			}
		})
	}
}

func setConfigEnv(t *testing.T) {
	t.Helper()
	for name, value := range map[string]string{
		"HTTP_ADDR":            "",
		"DATABASE_URL":         "postgres://localhost/db",
		"REDIS_URL":            "redis://localhost:6379",
		"S3_ENDPOINT":          "http://localhost:9000",
		"S3_PRESIGN_ENDPOINT":  "",
		"S3_REGION":            "",
		"S3_BUCKET":            "",
		"S3_ACCESS_KEY":        "key",
		"S3_SECRET_KEY":        "secret",
		"S3_FORCE_PATH_STYLE":  "",
		"SIGNED_URL_TTL":       "",
		"MAX_UPLOAD_BYTES":     "",
		"PIPELINE_VERSION":     "",
		"DETECTION_SAMPLE_FPS": "",
		"MODEL_VERSION":        "",
		"DEVELOPMENT_OWNER":    "",
		"WEB_BASE_URL":         "",
	} {
		t.Setenv(name, value)
	}
}
