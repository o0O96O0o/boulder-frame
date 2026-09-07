package config

import (
	"errors"
	"fmt"
	"math"
	"net/url"
	"os"
	"strconv"
	"time"
)

type Config struct {
	HTTPAddr           string
	DatabaseURL        string
	RedisURL           string
	S3Endpoint         string
	S3PresignEndpoint  string
	S3Region           string
	S3Bucket           string
	S3AccessKey        string
	S3SecretKey        string
	S3UsePathStyle     bool
	URLTTL             time.Duration
	MaxUploadBytes     int64
	PipelineVersion    string
	DetectionSampleFPS float64
	ModelVersion       string
	DevelopmentOwner   string
	WebBaseURL         string
}

const (
	localEnvUnconfiguredModelVersion = "unset-until-pinned"
	unconfiguredModelVersion         = "unconfigured"
)

func Load() (Config, error) {
	c := Config{
		HTTPAddr:          envOrDefault("HTTP_ADDR", ":8080"),
		DatabaseURL:       os.Getenv("DATABASE_URL"),
		RedisURL:          os.Getenv("REDIS_URL"),
		S3Endpoint:        os.Getenv("S3_ENDPOINT"),
		S3PresignEndpoint: os.Getenv("S3_PRESIGN_ENDPOINT"),
		S3Region:          os.Getenv("S3_REGION"),
		S3Bucket:          os.Getenv("S3_BUCKET"),
		S3AccessKey:       os.Getenv("S3_ACCESS_KEY"),
		S3SecretKey:       os.Getenv("S3_SECRET_KEY"),
		PipelineVersion:   os.Getenv("PIPELINE_VERSION"),
		ModelVersion:      os.Getenv("MODEL_VERSION"),
		DevelopmentOwner:  envOrDefault("DEVELOPMENT_OWNER", "deployment"),
		WebBaseURL:        os.Getenv("WEB_BASE_URL"),
	}
	if c.ModelVersion == localEnvUnconfiguredModelVersion {
		c.ModelVersion = unconfiguredModelVersion
	}
	var err error
	c.S3UsePathStyle, err = strconv.ParseBool(envOrDefault("S3_FORCE_PATH_STYLE", "true"))
	if err != nil {
		return Config{}, fmt.Errorf("S3_FORCE_PATH_STYLE must be a boolean: %w", err)
	}
	c.URLTTL, err = time.ParseDuration(envOrDefault("SIGNED_URL_TTL", "15m"))
	if err != nil {
		return Config{}, fmt.Errorf("SIGNED_URL_TTL must be a positive duration: %w", err)
	}
	if c.URLTTL <= 0 {
		return Config{}, errors.New("SIGNED_URL_TTL must be a positive duration")
	}
	c.MaxUploadBytes, err = strconv.ParseInt(envOrDefault("MAX_UPLOAD_BYTES", "2147483648"), 10, 64)
	if err != nil || c.MaxUploadBytes <= 0 {
		return Config{}, errors.New("MAX_UPLOAD_BYTES must be a positive integer")
	}
	c.DetectionSampleFPS, err = strconv.ParseFloat(envOrDefault("DETECTION_SAMPLE_FPS", "10"), 64)
	if err != nil || math.IsNaN(c.DetectionSampleFPS) || math.IsInf(c.DetectionSampleFPS, 0) || c.DetectionSampleFPS < 0 || c.DetectionSampleFPS > 1000 {
		return Config{}, errors.New("DETECTION_SAMPLE_FPS must be a finite number between 0 and 1000")
	}
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

func envOrDefault(name, fallback string) string {
	if value := os.Getenv(name); value != "" {
		return value
	}
	return fallback
}
