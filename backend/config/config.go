package config

import (
	"encoding/json"
	"errors"
	"fmt"
	"net/url"
	"os"
	"time"
)

type Config struct {
	SourcePath        string
	HTTPAddr          string
	DatabaseURL       string
	RedisURL          string
	S3Endpoint        string
	S3PresignEndpoint string
	S3Region          string
	S3Bucket          string
	S3AccessKey       string
	S3SecretKey       string
	S3UsePathStyle    bool
	URLTTL            time.Duration
	MaxUploadBytes    int64
	PipelineVersion   string
	ModelVersion      string
	DevelopmentOwner  string
	WebBaseURL        string
}

const (
	localEnvUnconfiguredModelVersion = "unset-until-pinned"
	unconfiguredModelVersion         = "unconfigured"
)

func Load(paths ...string) (Config, error) {
	path := "conf/config.json"
	if len(paths) > 0 && paths[0] != "" {
		path = paths[0]
	} else if _, err := os.Stat(path); errors.Is(err, os.ErrNotExist) {
		path = "backend/conf/config.json"
	}
	contents, err := os.ReadFile(path)
	if err != nil {
		return Config{}, fmt.Errorf("read configuration %q: %w", path, err)
	}
	var raw struct {
		HTTPAddr          string `json:"http_addr"`
		DatabaseURL       string `json:"database_url"`
		RedisURL          string `json:"redis_url"`
		S3Endpoint        string `json:"s3_endpoint"`
		S3PresignEndpoint string `json:"s3_presign_endpoint"`
		S3Region          string `json:"s3_region"`
		S3Bucket          string `json:"s3_bucket"`
		S3AccessKey       string `json:"s3_access_key"`
		S3SecretKey       string `json:"s3_secret_key"`
		S3UsePathStyle    bool   `json:"s3_use_path_style"`
		SignedURLTTL      string `json:"signed_url_ttl"`
		MaxUploadBytes    int64  `json:"max_upload_bytes"`
		PipelineVersion   string `json:"pipeline_version"`
		ModelVersion      string `json:"model_version"`
		DevelopmentOwner  string `json:"development_owner"`
		WebBaseURL        string `json:"web_base_url"`
	}
	contents = []byte(os.Expand(string(contents), os.Getenv))
	if err := json.Unmarshal(contents, &raw); err != nil {
		return Config{}, fmt.Errorf("parse configuration %q: %w", path, err)
	}
	c := Config{
		SourcePath: path,
		HTTPAddr:   raw.HTTPAddr, DatabaseURL: raw.DatabaseURL, RedisURL: raw.RedisURL,
		S3Endpoint: raw.S3Endpoint, S3PresignEndpoint: raw.S3PresignEndpoint,
		S3Region: raw.S3Region, S3Bucket: raw.S3Bucket, S3AccessKey: raw.S3AccessKey,
		S3SecretKey: raw.S3SecretKey, S3UsePathStyle: raw.S3UsePathStyle,
		PipelineVersion: raw.PipelineVersion, ModelVersion: raw.ModelVersion,
		DevelopmentOwner: raw.DevelopmentOwner, WebBaseURL: raw.WebBaseURL,
	}
	if c.ModelVersion == localEnvUnconfiguredModelVersion {
		c.ModelVersion = unconfiguredModelVersion
	}
	if c.HTTPAddr == "" {
		c.HTTPAddr = ":8080"
	}
	d, err := time.ParseDuration(raw.SignedURLTTL)
	if err != nil || d <= 0 {
		return Config{}, fmt.Errorf("signed_url_ttl must be a positive duration: %w", err)
	}
	c.URLTTL = d
	if raw.MaxUploadBytes <= 0 {
		return Config{}, errors.New("max_upload_bytes must be a positive integer")
	}
	c.MaxUploadBytes = raw.MaxUploadBytes
	for name, value := range map[string]string{"DATABASE_URL": c.DatabaseURL, "REDIS_URL": c.RedisURL, "S3_ENDPOINT": c.S3Endpoint, "S3_ACCESS_KEY": c.S3AccessKey, "S3_SECRET_KEY": c.S3SecretKey} {
		if value == "" {
			return Config{}, fmt.Errorf("%s is required", name)
		}
	}
	if u, err := url.Parse(c.DatabaseURL); err != nil || u.Scheme == "" {
		return Config{}, errors.New("DATABASE_URL must be a valid URL")
	}
	if u, err := url.Parse(c.RedisURL); err != nil || u.Scheme == "" {
		return Config{}, errors.New("REDIS_URL must be a valid URL")
	}
	if u, err := url.Parse(c.S3Endpoint); err != nil || u.Scheme == "" || u.Host == "" {
		return Config{}, errors.New("S3_ENDPOINT must be an absolute URL")
	}
	return c, nil
}
