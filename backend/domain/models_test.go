package domain

import (
	"encoding/json"
	"strings"
	"testing"

	"github.com/google/uuid"
)

func TestNewJobConfigValidatesContract(t *testing.T) {
	cases := []struct {
		name      string
		selection TargetSelection
		output    OutputSettings
		wantErr   bool
	}{
		{"valid", TargetSelection{FrameTimeMS: 20, NormalizedX: .5, NormalizedY: .2}, OutputSettings{"16:9", "balanced"}, false},
		{"negative time", TargetSelection{FrameTimeMS: -1, NormalizedX: .5, NormalizedY: .2}, OutputSettings{"16:9", "balanced"}, true},
		{"bad coordinate", TargetSelection{NormalizedX: 1.1, NormalizedY: .2}, OutputSettings{"16:9", "balanced"}, true},
		{"bad ratio", TargetSelection{NormalizedX: .5, NormalizedY: .2}, OutputSettings{"1:1", "balanced"}, true},
		{"bad profile", TargetSelection{NormalizedX: .5, NormalizedY: .2}, OutputSettings{"16:9", "wide"}, true},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			_, err := NewJobConfig(uuid.New(), tc.selection, tc.output, "pipeline", "model")
			if (err != nil) != tc.wantErr {
				t.Fatalf("error = %v, wantErr %v", err, tc.wantErr)
			}
		})
	}
}

func TestSourceMediaValidationAcceptsMP4AndQuickTimeMOV(t *testing.T) {
	cases := []struct {
		filename, contentType string
		want                  bool
	}{
		{"session.mp4", "video/mp4", true},
		{"session.MOV", "video/quicktime", true},
		{"session.mov", "video/mp4", false},
		{"session.mkv", "video/mp4", false},
	}
	for _, tc := range cases {
		t.Run(tc.filename+"/"+tc.contentType, func(t *testing.T) {
			if got := ValidSourceContentType(tc.filename, tc.contentType); got != tc.want {
				t.Fatalf("ValidSourceContentType() = %v, want %v", got, tc.want)
			}
		})
	}
}

func TestSourceStorageKeyRetainsSupportedExtension(t *testing.T) {
	project, asset := uuid.New(), uuid.New()
	if got := SourceStorageKey(project, asset, "session.MOV"); !strings.HasSuffix(got, "/"+asset.String()+".mov") {
		t.Fatalf("MOV storage key = %q", got)
	}
	if got := SourceStorageKey(project, asset, "session.mp4"); !strings.HasSuffix(got, "/"+asset.String()+".mp4") {
		t.Fatalf("MP4 storage key = %q", got)
	}
}

func TestJobConfigHashIsStableAndChangesWithConfiguration(t *testing.T) {
	c, err := NewJobConfig(uuid.New(), TargetSelection{NormalizedX: .5, NormalizedY: .5}, OutputSettings{"16:9", "balanced"}, "p1", "m1")
	if err != nil {
		t.Fatal(err)
	}
	a, _ := c.Hash()
	b, _ := c.Hash()
	if a != b {
		t.Fatal("same configuration produced different hashes")
	}
	c.Output.Profile = "safe"
	d, _ := c.Hash()
	if a == d {
		t.Fatal("different configuration produced same hash")
	}
}

func TestParseEvaluationManifestAcceptsWorkerCompatibleRootMetadata(t *testing.T) {
	reviewID := uuid.New()
	endMS := int64(20)
	manifest := map[string]any{
		"schema_version":   1,
		"review_id":        reviewID.String(),
		"pipeline_version": "w0.1.0",
		"model_version":    "w0.1-model",
		"timing":           map[string]any{"frame_rate": 60.0, "duration_ms": 1200, "frame_count": 72},
		"telemetry":        map[string]any{"status": "ready"},
		"phases": []any{
			map[string]any{"id": "measurement", "status": "ready", "summary": map[string]any{"selected_rate": .9, "mapping_verified": false, "first_warning": nil}},
			map[string]any{"id": "pose", "status": "partial"},
			map[string]any{"id": "tracking", "status": "warning", "warning_intervals": []any{map[string]any{"start_ms": 10, "end_ms": endMS, "label": "Tracking lost", "detail": "Subject was briefly occluded"}}},
			map[string]any{"id": "planning", "status": "unavailable", "detail": "Review capture exceeded its duration limit"},
			map[string]any{"id": "render", "status": "warning", "warning_intervals": []any{map[string]any{"start_ms": 1200, "label": "At source end"}}},
		},
	}
	data, err := json.Marshal(manifest)
	if err != nil {
		t.Fatal(err)
	}
	got, err := ParseEvaluationManifest(data)
	if err != nil || got.ReviewID != reviewID || got.PipelineVersion != "w0.1.0" || got.ModelVersion != "w0.1-model" || got.Timing.FrameRate != 60 || got.Timing.DurationMS != 1200 || got.Timing.FrameCount != 72 || !got.TelemetryReady || len(got.Phases) != 5 || got.Phases[2].WarningIntervals[0].EndMS == nil || *got.Phases[2].WarningIntervals[0].EndMS != endMS || got.Phases[3].Detail != "Review capture exceeded its duration limit" || got.Phases[4].WarningIntervals[0].StartMS != 1200 || got.Phases[4].WarningIntervals[0].EndMS != nil {
		t.Fatalf("ParseEvaluationManifest() = %#v, %v", got, err)
	}
}

func TestParseEvaluationManifestRejectsUnsafeOrUnorderedData(t *testing.T) {
	reviewID := uuid.New().String()
	validManifest := map[string]any{"schema_version": 1, "review_id": reviewID, "pipeline_version": "w0.1.0", "model_version": "w0.1-model", "timing": map[string]any{"frame_rate": 60.0, "duration_ms": 1200, "frame_count": 72}}
	validPhases := []map[string]any{
		{"id": "measurement", "status": "ready"}, {"id": "pose", "status": "ready"}, {"id": "tracking", "status": "ready"}, {"id": "planning", "status": "ready"}, {"id": "render", "status": "ready"},
	}
	for _, manifest := range []map[string]any{
		{"schema_version": 1, "review_id": reviewID, "phases": []map[string]any{{"id": "pose", "status": "ready"}}},
		{"schema_version": 1, "review_id": reviewID, "phases": []map[string]any{{"id": "measurement", "status": "ready"}, {"id": "pose", "status": "ready"}, {"id": "tracking", "status": "ready"}, {"id": "planning", "status": "ready"}, {"id": "render", "status": "ready", "summary": map[string]any{"storage_key": "private/secret"}}}},
		{"schema_version": 1, "review_id": reviewID, "phases": []map[string]any{{"id": "measurement", "status": "ready", "warning_intervals": []any{map[string]any{"start_ms": 1, "label": "Signed URL", "detail": "https://storage.test/object?X-Amz-Signature=secret"}}}, validPhases[1], validPhases[2], validPhases[3], validPhases[4]}},
		{"schema_version": 1, "review_id": reviewID, "phases": []map[string]any{{"id": "measurement", "status": "ready", "summary": map[string]any{"operator_note": "Bearer eyJhbGciOiJIUzI1NiJ9.payload.signature"}}, validPhases[1], validPhases[2], validPhases[3], validPhases[4]}},
		{"schema_version": 1, "review_id": reviewID, "phases": []map[string]any{{"id": "measurement", "status": "unavailable", "detail": "https://storage.test/private/debug?X-Amz-Signature=secret"}, validPhases[1], validPhases[2], validPhases[3], validPhases[4]}},
		{"schema_version": 1, "review_id": reviewID, "phases": []map[string]any{{"id": "measurement", "status": "ready", "detail": "Capture unavailable"}, validPhases[1], validPhases[2], validPhases[3], validPhases[4]}},
		{"schema_version": 1, "review_id": reviewID, "phases": []map[string]any{{"id": "measurement", "status": "unavailable", "detail": map[string]any{"reason": "Capture unavailable"}}, validPhases[1], validPhases[2], validPhases[3], validPhases[4]}},
		{"schema_version": 1, "review_id": reviewID, "phases": []map[string]any{{"id": "measurement", "status": "unavailable", "detail": "Capture unavailable", "debug": true}, validPhases[1], validPhases[2], validPhases[3], validPhases[4]}},
		{"schema_version": 1, "review_id": reviewID, "pipeline_version": "https://storage.test", "model_version": "w0.1-model", "timing": map[string]any{"frame_rate": 60.0, "duration_ms": 1200, "frame_count": 72}, "phases": validPhases},
		{"schema_version": 1, "review_id": reviewID, "pipeline_version": "w0.1.0", "model_version": "w0.1-model", "timing": map[string]any{"frame_rate": 0, "duration_ms": 1200, "frame_count": 72}, "phases": validPhases},
	} {
		for key, value := range validManifest {
			if _, exists := manifest[key]; !exists {
				manifest[key] = value
			}
		}
		data, err := json.Marshal(manifest)
		if err != nil {
			t.Fatal(err)
		}
		if _, err := ParseEvaluationManifest(data); err == nil {
			t.Fatalf("unsafe manifest was accepted: %s", data)
		}
	}
}

func TestParseEvaluationManifestRejectsInvalidWarningIntervals(t *testing.T) {
	reviewID := uuid.New().String()
	for _, interval := range []map[string]any{
		{"start_ms": -1, "label": "Invalid"},
		{"start_ms": 1201, "label": "Beyond source end"},
		{"start_ms": 1200, "end_ms": 1201, "label": "Beyond source end"},
		{"start_ms": 20, "end_ms": 10, "label": "Reversed"},
	} {
		phases := []map[string]any{
			{"id": "measurement", "status": "warning", "warning_intervals": []any{interval}},
			{"id": "pose", "status": "ready"}, {"id": "tracking", "status": "ready"}, {"id": "planning", "status": "ready"}, {"id": "render", "status": "ready"},
		}
		data, err := json.Marshal(map[string]any{"schema_version": 1, "review_id": reviewID, "pipeline_version": "w0.1.0", "model_version": "w0.1-model", "timing": map[string]any{"frame_rate": 60.0, "duration_ms": 1200, "frame_count": 72}, "phases": phases})
		if err != nil {
			t.Fatal(err)
		}
		if _, err := ParseEvaluationManifest(data); err == nil {
			t.Fatalf("manifest with invalid warning interval was accepted: %s", data)
		}
	}
}
