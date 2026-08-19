package domain

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"
)

const (
	OwnerDevelopment = "development-owner"
	AssetSource      = "source"
	AssetOutput      = "output"
	AssetDebug       = "debug"
	UploadPending    = "pending"
	UploadUploaded   = "uploaded"
	UploadInvalid    = "invalid"
	JobQueued        = "queued"
	JobValidating    = "validating"
	JobAnalyzing     = "analyzing"
	JobRendering     = "rendering"
	JobUploading     = "uploading"
	JobCompleted     = "completed"
	JobFailed        = "failed"
	JobCancelled     = "cancelled"
)

type Project struct {
	ID        uuid.UUID `json:"id"`
	Name      string    `json:"name"`
	OwnerID   string    `json:"-"`
	CreatedAt time.Time `json:"created_at"`
}
type Asset struct {
	ID          uuid.UUID `json:"id"`
	ProjectID   uuid.UUID `json:"project_id"`
	Kind        string    `json:"kind"`
	StorageKey  string    `json:"storage_key"`
	UploadState string    `json:"upload_state"`
	Filename    string    `json:"filename,omitempty"`
	ContentType string    `json:"content_type,omitempty"`
	SizeBytes   int64     `json:"size_bytes,omitempty"`
	Width       int       `json:"width,omitempty"`
	Height      int       `json:"height,omitempty"`
	FrameRate   float64   `json:"frame_rate,omitempty"`
	DurationMS  int64     `json:"duration_ms,omitempty"`
	CreatedAt   time.Time `json:"created_at"`
}
type TargetSelection struct {
	FrameTimeMS int64   `json:"frame_time_ms"`
	NormalizedX float64 `json:"normalized_x"`
	NormalizedY float64 `json:"normalized_y"`
}
type OutputSettings struct {
	AspectRatio string `json:"aspect_ratio"`
	Profile     string `json:"profile"`
}
type JobConfig struct {
	SourceAssetID   uuid.UUID       `json:"source_asset_id"`
	TargetSelection TargetSelection `json:"target_selection"`
	Output          OutputSettings  `json:"output"`
	PipelineVersion string          `json:"pipeline_version"`
	ModelVersion    string          `json:"model_version"`
	Planner         map[string]any  `json:"planner"`
}
type JobError struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}
type Job struct {
	ID            uuid.UUID  `json:"id"`
	ProjectID     uuid.UUID  `json:"project_id"`
	SourceAssetID uuid.UUID  `json:"source_asset_id"`
	State         string     `json:"state"`
	Stage         string     `json:"stage"`
	Progress      int        `json:"progress"`
	Configuration JobConfig  `json:"configuration"`
	OutputAssetID *uuid.UUID `json:"output_asset_id"`
	Error         *JobError  `json:"error"`
	CreatedAt     time.Time  `json:"created_at"`
	StartedAt     *time.Time `json:"started_at"`
	CompletedAt   *time.Time `json:"completed_at"`
}
type Artifact struct {
	ID        uuid.UUID `json:"id"`
	JobID     uuid.UUID `json:"job_id"`
	AssetID   uuid.UUID `json:"asset_id"`
	Kind      string    `json:"kind"`
	CreatedAt time.Time `json:"created_at"`
}

func NewJobConfig(source uuid.UUID, selection TargetSelection, output OutputSettings, pipeline, model string) (JobConfig, error) {
	if selection.FrameTimeMS < 0 || selection.NormalizedX < 0 || selection.NormalizedX > 1 || selection.NormalizedY < 0 || selection.NormalizedY > 1 {
		return JobConfig{}, errors.New("target selection is outside supported bounds")
	}
	if output.AspectRatio != "16:9" && output.AspectRatio != "9:16" {
		return JobConfig{}, errors.New("aspect_ratio must be 16:9 or 9:16")
	}
	if !map[string]bool{"tight": true, "balanced": true, "safe": true, "full_movement": true}[output.Profile] {
		return JobConfig{}, errors.New("profile is unsupported")
	}
	return JobConfig{SourceAssetID: source, TargetSelection: selection, Output: output, PipelineVersion: pipeline, ModelVersion: model, Planner: map[string]any{"controller": "deterministic-v1"}}, nil
}

func (c JobConfig) Hash() (string, error) {
	b, err := json.Marshal(c)
	if err != nil {
		return "", err
	}
	sum := sha256.Sum256(b)
	return hex.EncodeToString(sum[:]), nil
}
func ValidSourceFilename(name string) bool {
	lower := strings.ToLower(name)
	return strings.HasSuffix(lower, ".mp4") || strings.HasSuffix(lower, ".mov")
}
func ValidSourceContentType(filename, contentType string) bool {
	lower := strings.ToLower(filename)
	switch {
	case strings.HasSuffix(lower, ".mp4"):
		return contentType == "video/mp4"
	case strings.HasSuffix(lower, ".mov"):
		return contentType == "video/quicktime"
	default:
		return false
	}
}
func SourceStorageKey(project, asset uuid.UUID, filename string) string {
	extension := ".mp4"
	if strings.HasSuffix(strings.ToLower(filename), ".mov") {
		extension = ".mov"
	}
	return fmt.Sprintf("private/source/%s/%s%s", project, asset, extension)
}
