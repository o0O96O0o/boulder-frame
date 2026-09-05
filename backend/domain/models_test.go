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
	pipelineChanged := c
	pipelineChanged.PipelineVersion = "p2"
	pipelineHash, _ := pipelineChanged.Hash()
	if a == pipelineHash {
		t.Fatal("pipeline-version-only change produced same hash")
	}
	c.Output.Profile = "safe"
	d, _ := c.Hash()
	if a == d {
		t.Fatal("different configuration produced same hash")
	}
}

func TestJobConfigHashSeparatesPlannerVersionsAndMotionConstants(t *testing.T) {
	source := uuid.New()
	selection := TargetSelection{NormalizedX: .5, NormalizedY: .5}
	output := OutputSettings{"16:9", "balanced"}
	config, err := NewJobConfig(source, selection, output, "w0.2.3", "m1")
	if err != nil {
		t.Fatal(err)
	}
	currentHash, err := config.Hash()
	if err != nil {
		t.Fatal(err)
	}
	legacy := config
	legacy.PipelineVersion = "w0.2.2"
	legacy.Planner = map[string]any{
		"controller":            "deterministic-v2",
		"scale_enter_fraction":  0.05,
		"scale_exit_fraction":   0.02,
		"center_enter_fraction": 0.01,
		"center_exit_fraction":  0.004,
	}
	legacyHash, err := legacy.Hash()
	if err != nil {
		t.Fatal(err)
	}
	if currentHash == legacyHash {
		t.Fatal("planner cutover reused the legacy job hash")
	}

	expected := map[string]any{
		"controller":            "deterministic-v3",
		"scale_enter_fraction":  0.05,
		"scale_exit_fraction":   0.02,
		"center_enter_fraction": 0.01,
		"center_exit_fraction":  0.004,
		"zoom_max_speed":        0.5,
		"zoom_max_acceleration": 1.0,
		"pan_max_speed":         0.25,
		"pan_max_acceleration":  0.5,
	}
	for key, value := range expected {
		t.Run(key, func(t *testing.T) {
			if config.Planner[key] != value {
				t.Fatalf("immutable planner %s = %v, want %v", key, config.Planner[key], value)
			}
			changed, err := NewJobConfig(source, selection, output, "w0.2.3", "m1")
			if err != nil {
				t.Fatal(err)
			}
			if key == "controller" {
				changed.Planner[key] = "deterministic-v2"
			} else {
				changed.Planner[key] = value.(float64) * 2
			}
			changedHash, err := changed.Hash()
			if err != nil {
				t.Fatal(err)
			}
			if changedHash == currentHash {
				t.Fatalf("changing planner %s reused the same job hash", key)
			}
			unchangedHash, err := config.Hash()
			if err != nil {
				t.Fatal(err)
			}
			if unchangedHash != currentHash {
				t.Fatal("another job's planner mutation changed the original configuration")
			}
		})
	}
}

func TestParseEvaluationManifestAcceptsWorkerCompatibleRootMetadata(t *testing.T) {
	reviewID := uuid.New()
	endMS := int64(20)
	manifest := map[string]any{
		"schema_version":   1,
		"review_id":        reviewID.String(),
		"pipeline_version": "w0.2.0",
		"model_version":    "w0.2-ssd-mobilenetv1-12-onnx-detector-only-1",
		"timing":           map[string]any{"frame_rate": 60.0, "duration_ms": 1200, "frame_count": 72},
		"telemetry":        map[string]any{"status": "ready"},
		"phases": []any{
			map[string]any{"id": "detection", "status": "ready", "summary": map[string]any{"detected_frames": 72, "detection_rate": .9, "first_warning": nil}},
			map[string]any{"id": "framing", "status": "warning", "warning_intervals": []any{map[string]any{"start_ms": 10, "end_ms": endMS, "label": "Detection missed", "detail": "The crop widened toward the full frame."}}},
			map[string]any{"id": "render", "status": "warning", "warning_intervals": []any{map[string]any{"start_ms": 1200, "label": "At source end"}}},
		},
	}
	data, err := json.Marshal(manifest)
	if err != nil {
		t.Fatal(err)
	}
	got, err := ParseEvaluationManifest(data)
	if err != nil || got.ReviewID != reviewID || got.PipelineVersion != "w0.2.0" || got.ModelVersion != "w0.2-ssd-mobilenetv1-12-onnx-detector-only-1" || got.Timing.FrameRate != 60 || got.Timing.DurationMS != 1200 || got.Timing.FrameCount != 72 || !got.TelemetryReady || len(got.Phases) != 3 || got.Phases[1].WarningIntervals[0].EndMS == nil || *got.Phases[1].WarningIntervals[0].EndMS != endMS || got.Phases[2].WarningIntervals[0].StartMS != 1200 || got.Phases[2].WarningIntervals[0].EndMS != nil {
		t.Fatalf("ParseEvaluationManifest() = %#v, %v", got, err)
	}
}

func TestParseEvaluationManifestRejectsUnsafeOrUnorderedData(t *testing.T) {
	reviewID := uuid.New().String()
	validManifest := map[string]any{"schema_version": 1, "review_id": reviewID, "pipeline_version": "w0.2.0", "model_version": "w0.2-ssd-mobilenetv1-12-onnx-detector-only-1", "timing": map[string]any{"frame_rate": 60.0, "duration_ms": 1200, "frame_count": 72}}
	validPhases := []map[string]any{
		{"id": "detection", "status": "ready"}, {"id": "framing", "status": "ready"}, {"id": "render", "status": "ready"},
	}
	for _, manifest := range []map[string]any{
		{"schema_version": 1, "review_id": reviewID, "phases": []map[string]any{{"id": "framing", "status": "ready"}}},
		{"schema_version": 1, "review_id": reviewID, "phases": []map[string]any{{"id": "detection", "status": "ready"}, {"id": "framing", "status": "ready"}, {"id": "render", "status": "ready", "summary": map[string]any{"storage_key": "private/secret"}}}},
		{"schema_version": 1, "review_id": reviewID, "phases": []map[string]any{{"id": "detection", "status": "ready", "warning_intervals": []any{map[string]any{"start_ms": 1, "label": "Signed URL", "detail": "https://storage.test/object?X-Amz-Signature=secret"}}}, validPhases[1], validPhases[2]}},
		{"schema_version": 1, "review_id": reviewID, "phases": []map[string]any{{"id": "detection", "status": "ready", "summary": map[string]any{"operator_note": "Bearer eyJhbGciOiJIUzI1NiJ9.payload.signature"}}, validPhases[1], validPhases[2]}},
		{"schema_version": 1, "review_id": reviewID, "phases": []map[string]any{{"id": "detection", "status": "unavailable", "detail": "https://storage.test/private/debug?X-Amz-Signature=secret"}, validPhases[1], validPhases[2]}},
		{"schema_version": 1, "review_id": reviewID, "phases": []map[string]any{{"id": "detection", "status": "ready", "detail": "Capture unavailable"}, validPhases[1], validPhases[2]}},
		{"schema_version": 1, "review_id": reviewID, "phases": []map[string]any{{"id": "detection", "status": "unavailable", "detail": map[string]any{"reason": "Capture unavailable"}}, validPhases[1], validPhases[2]}},
		{"schema_version": 1, "review_id": reviewID, "phases": []map[string]any{{"id": "detection", "status": "unavailable", "detail": "Capture unavailable", "debug": true}, validPhases[1], validPhases[2]}},
		{"schema_version": 1, "review_id": reviewID, "pipeline_version": "https://storage.test", "model_version": "w0.2-model", "timing": map[string]any{"frame_rate": 60.0, "duration_ms": 1200, "frame_count": 72}, "phases": validPhases},
		{"schema_version": 1, "review_id": reviewID, "pipeline_version": "w0.2.0", "model_version": "w0.2-model", "timing": map[string]any{"frame_rate": 0, "duration_ms": 1200, "frame_count": 72}, "phases": validPhases},
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
			{"id": "detection", "status": "warning", "warning_intervals": []any{interval}},
			{"id": "framing", "status": "ready"}, {"id": "render", "status": "ready"},
		}
		data, err := json.Marshal(map[string]any{"schema_version": 1, "review_id": reviewID, "pipeline_version": "w0.2.0", "model_version": "w0.2-model", "timing": map[string]any{"frame_rate": 60.0, "duration_ms": 1200, "frame_count": 72}, "phases": phases})
		if err != nil {
			t.Fatal(err)
		}
		if _, err := ParseEvaluationManifest(data); err == nil {
			t.Fatalf("manifest with invalid warning interval was accepted: %s", data)
		}
	}
}
