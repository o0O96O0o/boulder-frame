package domain

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math"
	"regexp"
	"strings"
	"time"

	"github.com/google/uuid"
)

const (
	OwnerDevelopment         = "development-owner"
	AssetSource              = "source"
	AssetOutput              = "output"
	AssetDebug               = "debug"
	ArtifactOutput           = "output"
	ArtifactDebugTelemetry   = "debug_telemetry"
	ArtifactDebugManifest    = "debug_manifest"
	ArtifactDebugMeasurement = "debug_measurement"
	ArtifactDebugPose        = "debug_pose"
	ArtifactDebugTracking    = "debug_tracking"
	ArtifactDebugPlanning    = "debug_planning"
	ArtifactDebugRender      = "debug_render"
	UploadPending            = "pending"
	UploadUploaded           = "uploaded"
	UploadInvalid            = "invalid"
	JobQueued                = "queued"
	JobValidating            = "validating"
	JobAnalyzing             = "analyzing"
	JobRendering             = "rendering"
	JobUploading             = "uploading"
	JobCompleted             = "completed"
	JobFailed                = "failed"
	JobCancelled             = "cancelled"
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
type ReviewArtifact struct {
	Role  string
	Asset Asset
}
type Evaluation struct {
	Available            bool              `json:"available"`
	ReviewID             string            `json:"review_id,omitempty"`
	State                string            `json:"state,omitempty"`
	PipelineVersion      string            `json:"pipeline_version,omitempty"`
	ModelVersion         string            `json:"model_version,omitempty"`
	Timing               *EvaluationTiming `json:"timing,omitempty"`
	Phases               []EvaluationPhase `json:"phases,omitempty"`
	TelemetryDownloadURL string            `json:"telemetry_download_url,omitempty"`
	ExpiresInSeconds     int               `json:"expires_in_seconds,omitempty"`
}
type EvaluationTiming struct {
	FrameRate  float64 `json:"frame_rate"`
	DurationMS int64   `json:"duration_ms"`
	FrameCount int64   `json:"frame_count"`
}
type EvaluationPhase struct {
	ID               string            `json:"id"`
	Label            string            `json:"label"`
	Status           string            `json:"status"`
	Detail           string            `json:"detail,omitempty"`
	Summary          map[string]any    `json:"summary,omitempty"`
	WarningIntervals []WarningInterval `json:"warning_intervals,omitempty"`
	VideoURL         string            `json:"video_url,omitempty"`
}
type WarningInterval struct {
	StartMS int64  `json:"start_ms"`
	EndMS   *int64 `json:"end_ms,omitempty"`
	Label   string `json:"label"`
	Detail  string `json:"detail,omitempty"`
}
type EvaluationManifest struct {
	ReviewID        uuid.UUID
	PipelineVersion string
	ModelVersion    string
	Timing          EvaluationTiming
	Phases          []ManifestPhase
	TelemetryReady  bool
}
type ManifestPhase struct {
	ID               string
	Status           string
	Detail           string
	Summary          map[string]any
	WarningIntervals []WarningInterval
}

var (
	reviewPhaseOrder = []string{"measurement", "pose", "tracking", "planning", "render"}
	summaryFieldName = regexp.MustCompile(`^[a-z][a-z0-9_]{0,63}$`)
)

const (
	maxManifestVersionLength = 128
	maxManifestDurationMS    = 7 * 24 * 60 * 60 * 1000
	maxManifestFrameCount    = 10_000_000
)

func ValidArtifactKind(kind string) bool {
	return map[string]bool{
		ArtifactOutput: true, ArtifactDebugTelemetry: true, ArtifactDebugManifest: true,
		ArtifactDebugMeasurement: true, ArtifactDebugPose: true, ArtifactDebugTracking: true,
		ArtifactDebugPlanning: true, ArtifactDebugRender: true,
	}[kind]
}
func ValidReviewArtifactRole(role string) bool {
	return role == ArtifactDebugTelemetry || role == ArtifactDebugManifest ||
		role == ArtifactDebugMeasurement || role == ArtifactDebugPose ||
		role == ArtifactDebugTracking || role == ArtifactDebugPlanning || role == ArtifactDebugRender
}
func ReviewArtifactRoleForPhase(phase string) string {
	return "debug_" + phase
}
func ReviewPhaseLabel(phase string) string {
	return map[string]string{
		"measurement": "Measurement", "pose": "Pose", "tracking": "Tracking", "planning": "Planning", "render": "Render",
	}[phase]
}
func ParseEvaluationManifest(data []byte) (EvaluationManifest, error) {
	var raw struct {
		SchemaVersion   int    `json:"schema_version"`
		ReviewID        string `json:"review_id"`
		PipelineVersion string `json:"pipeline_version"`
		ModelVersion    string `json:"model_version"`
		Timing          *struct {
			FrameRate  *float64 `json:"frame_rate"`
			DurationMS *int64   `json:"duration_ms"`
			FrameCount *int64   `json:"frame_count"`
		} `json:"timing"`
		Phases []struct {
			ID               string         `json:"id"`
			Status           string         `json:"status"`
			Detail           *string        `json:"detail"`
			Summary          map[string]any `json:"summary"`
			WarningIntervals []struct {
				StartMS *int64 `json:"start_ms"`
				EndMS   *int64 `json:"end_ms"`
				Label   string `json:"label"`
				Detail  string `json:"detail"`
			} `json:"warning_intervals"`
		} `json:"phases"`
		Telemetry *struct {
			Status string `json:"status"`
		} `json:"telemetry"`
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&raw); err != nil || decoder.Decode(&struct{}{}) != io.EOF {
		return EvaluationManifest{}, errors.New("invalid evaluation manifest")
	}
	if raw.SchemaVersion != 1 {
		return EvaluationManifest{}, errors.New("unsupported evaluation manifest schema")
	}
	reviewID, err := uuid.Parse(raw.ReviewID)
	if err != nil {
		return EvaluationManifest{}, errors.New("invalid evaluation review ID")
	}
	if !safeManifestText(raw.PipelineVersion, maxManifestVersionLength) || !safeManifestText(raw.ModelVersion, maxManifestVersionLength) || raw.Timing == nil ||
		raw.Timing.FrameRate == nil || *raw.Timing.FrameRate <= 0 || *raw.Timing.FrameRate > 1000 || math.IsNaN(*raw.Timing.FrameRate) || math.IsInf(*raw.Timing.FrameRate, 0) ||
		raw.Timing.DurationMS == nil || *raw.Timing.DurationMS <= 0 || *raw.Timing.DurationMS > maxManifestDurationMS ||
		raw.Timing.FrameCount == nil || *raw.Timing.FrameCount <= 0 || *raw.Timing.FrameCount > maxManifestFrameCount {
		return EvaluationManifest{}, errors.New("invalid evaluation metadata")
	}
	if len(raw.Phases) != len(reviewPhaseOrder) || (raw.Telemetry != nil && !validTelemetryStatus(raw.Telemetry.Status)) {
		return EvaluationManifest{}, errors.New("invalid evaluation phases")
	}
	seen := make(map[string]bool, len(raw.Phases))
	result := EvaluationManifest{
		ReviewID:        reviewID,
		PipelineVersion: raw.PipelineVersion,
		ModelVersion:    raw.ModelVersion,
		Timing: EvaluationTiming{
			FrameRate:  *raw.Timing.FrameRate,
			DurationMS: *raw.Timing.DurationMS,
			FrameCount: *raw.Timing.FrameCount,
		},
	}
	for index, phase := range raw.Phases {
		intervals, ok := validWarningIntervals(phase.WarningIntervals)
		if phase.ID != reviewPhaseOrder[index] || seen[phase.ID] || !validPhaseStatus(phase.Status) ||
			(phase.Detail != nil && (phase.Status != "unavailable" || !safeManifestText(*phase.Detail, 500))) ||
			!validSummary(phase.Summary) || !ok {
			return EvaluationManifest{}, errors.New("invalid evaluation phase")
		}
		seen[phase.ID] = true
		detail := ""
		if phase.Detail != nil {
			detail = *phase.Detail
		}
		result.Phases = append(result.Phases, ManifestPhase{ID: phase.ID, Status: phase.Status, Detail: detail, Summary: phase.Summary, WarningIntervals: intervals})
	}
	result.TelemetryReady = raw.Telemetry != nil && raw.Telemetry.Status == "ready"
	return result, nil
}
func validPhaseStatus(status string) bool {
	return status == "ready" || status == "partial" || status == "unavailable" || status == "warning"
}
func validTelemetryStatus(status string) bool {
	return status == "ready" || status == "unavailable"
}
func validSummary(summary map[string]any) bool {
	if len(summary) > 32 {
		return false
	}
	for key, value := range summary {
		if !summaryFieldName.MatchString(key) || unsafeManifestField(key) {
			return false
		}
		switch v := value.(type) {
		case string:
			if !safeManifestText(v, 500) {
				return false
			}
		case bool:
		case float64:
			if math.IsNaN(v) || math.IsInf(v, 0) {
				return false
			}
		case nil:
		default:
			return false
		}
	}
	return true
}
func validWarningIntervals(raw []struct {
	StartMS *int64 `json:"start_ms"`
	EndMS   *int64 `json:"end_ms"`
	Label   string `json:"label"`
	Detail  string `json:"detail"`
}) ([]WarningInterval, bool) {
	intervals := make([]WarningInterval, 0, len(raw))
	if len(raw) > 100 {
		return nil, false
	}
	for _, interval := range raw {
		if interval.StartMS == nil || *interval.StartMS < 0 || (interval.EndMS != nil && *interval.EndMS < *interval.StartMS) || !safeManifestText(interval.Label, 120) || (interval.Detail != "" && !safeManifestText(interval.Detail, 500)) {
			return nil, false
		}
		intervals = append(intervals, WarningInterval{StartMS: *interval.StartMS, EndMS: interval.EndMS, Label: interval.Label, Detail: interval.Detail})
	}
	return intervals, true
}
func unsafeManifestField(field string) bool {
	field = strings.NewReplacer("_", "", "-", "", ".", "").Replace(strings.ToLower(field))
	return strings.Contains(field, "url") || strings.Contains(field, "uri") || strings.Contains(field, "href") ||
		strings.Contains(field, "token") || strings.Contains(field, "secret") || strings.Contains(field, "password") ||
		strings.Contains(field, "credential") || strings.Contains(field, "authorization") || strings.Contains(field, "cookie") ||
		strings.Contains(field, "signature") || strings.Contains(field, "accesskey") || strings.Contains(field, "storagekey") ||
		strings.Contains(field, "objectkey") || strings.Contains(field, "endpoint")
}
func safeManifestText(value string, maxLen int) bool {
	if value == "" || len(value) > maxLen {
		return false
	}
	lower := strings.ToLower(value)
	if strings.ContainsAny(value, "\x00\r\n\t") || strings.Contains(lower, "://") || strings.Contains(lower, "www.") ||
		strings.Contains(lower, "x-amz-") || strings.Contains(lower, "private/debug/") || strings.Contains(lower, "access_key") ||
		strings.Contains(lower, "secret") || strings.Contains(lower, "token") || strings.Contains(lower, "password") ||
		strings.Contains(lower, "authorization") || strings.Contains(lower, "credential") || strings.Contains(lower, "signature") ||
		regexp.MustCompile(`(?i)\b(akia|asia)[a-z0-9]{16}\b`).MatchString(value) ||
		regexp.MustCompile(`(?i)\b(bearer|basic)\s+[a-z0-9._~+/=-]+`).MatchString(value) {
		return false
	}
	return true
}
func ValidReviewStorageKey(key string, projectID, jobID, reviewID uuid.UUID, name string) bool {
	return key == fmt.Sprintf("private/debug/%s/%s/%s/%s", projectID, jobID, reviewID, name)
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
