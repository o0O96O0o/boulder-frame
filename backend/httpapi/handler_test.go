package httpapi

import (
	"bytes"
	"context"
	"errors"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/boulder-frame/backend/domain"
	"github.com/boulder-frame/backend/repository"
	"github.com/boulder-frame/backend/storage"
	"github.com/google/uuid"
)

type fakeRepo struct {
	project         domain.Project
	asset           domain.Asset
	job             domain.Job
	reviewArtifacts []domain.ReviewArtifact
	published       bool
	failPing        bool
	projectErr      error
	jobErr          error
	reviewErr       error
}

func (f *fakeRepo) Ping(context.Context) error {
	if f.failPing {
		return errors.New("down")
	}
	return nil
}
func (f *fakeRepo) CreateProject(context.Context, string, string) (domain.Project, error) {
	return f.project, nil
}
func (f *fakeRepo) GetProject(context.Context, uuid.UUID, string) (domain.Project, error) {
	if f.projectErr != nil {
		return domain.Project{}, f.projectErr
	}
	if f.project.ID == uuid.Nil || f.project.ID != uuid.Nil && f.project.ID != uuid.MustParse("00000000-0000-0000-0000-000000000001") {
		return domain.Project{}, repository.ErrNotFound
	}
	return f.project, nil
}
func (f *fakeRepo) CreateSourceAsset(context.Context, uuid.UUID, uuid.UUID, string, string, int64, string) (domain.Asset, error) {
	return f.asset, nil
}
func (f *fakeRepo) GetAsset(context.Context, uuid.UUID) (domain.Asset, error) {
	if f.asset.ID == uuid.Nil {
		return domain.Asset{}, repository.ErrNotFound
	}
	return f.asset, nil
}
func (f *fakeRepo) MarkAssetUploaded(context.Context, uuid.UUID, int64, string) (domain.Asset, error) {
	f.asset.UploadState = domain.UploadUploaded
	return f.asset, nil
}
func (f *fakeRepo) CreateOrGetJob(context.Context, domain.Job, string) (domain.Job, bool, error) {
	f.job = domain.Job{ID: uuid.New(), State: domain.JobQueued, Stage: domain.JobQueued}
	return f.job, false, nil
}
func (f *fakeRepo) GetJob(context.Context, uuid.UUID) (domain.Job, error) { return f.job, f.jobErr }
func (f *fakeRepo) ListArtifacts(context.Context, uuid.UUID) ([]domain.Artifact, error) {
	return []domain.Artifact{}, nil
}
func (f *fakeRepo) ListReviewArtifacts(context.Context, uuid.UUID) ([]domain.ReviewArtifact, error) {
	return f.reviewArtifacts, f.reviewErr
}
func (f *fakeRepo) SetJobFailed(context.Context, uuid.UUID, string, string) error { return nil }

type fakeStore struct {
	manifest   []byte
	readInfo   storage.ObjectInfo
	readErr    error
	presignErr error
}

func (fakeStore) PresignUpload(context.Context, string, string, time.Duration) (string, error) {
	return "https://upload.test", nil
}
func (f fakeStore) PresignDownload(context.Context, string, time.Duration) (string, error) {
	if f.presignErr != nil {
		return "", f.presignErr
	}
	return "https://download.test", nil
}
func (fakeStore) Head(context.Context, string) (storage.ObjectInfo, error) {
	return storage.ObjectInfo{}, nil
}
func (f fakeStore) Read(context.Context, string, int64) ([]byte, storage.ObjectInfo, error) {
	return f.manifest, f.readInfo, f.readErr
}

type fakeQueue struct{ count int }

func (f *fakeQueue) Publish(context.Context, string) error { f.count++; return nil }

func TestHealthAndReadiness(t *testing.T) {
	repo := &fakeRepo{}
	h := &Handler{Repo: repo}
	srv := httptest.NewServer(h.Router())
	defer srv.Close()
	for _, path := range []string{"/healthz", "/readyz"} {
		res, err := http.Get(srv.URL + path)
		if err != nil {
			t.Fatal(err)
		}
		if res.StatusCode != 200 {
			t.Fatalf("%s status %d", path, res.StatusCode)
		}
	}
	repo.failPing = true
	res, _ := http.Get(srv.URL + "/readyz")
	if res.StatusCode != 503 {
		t.Fatalf("readiness status %d", res.StatusCode)
	}
}

func TestCORSAllowsConfiguredWebOrigin(t *testing.T) {
	h := &Handler{Repo: &fakeRepo{}, WebBaseURL: "http://76.13.185.64:5173"}
	req := httptest.NewRequest(http.MethodOptions, "/api/v1/projects", nil)
	req.Header.Set("Origin", h.WebBaseURL)
	rec := httptest.NewRecorder()
	h.Router().ServeHTTP(rec, req)
	if rec.Code != http.StatusNoContent || rec.Header().Get("Access-Control-Allow-Origin") != h.WebBaseURL {
		t.Fatalf("status %d allow-origin %q", rec.Code, rec.Header().Get("Access-Control-Allow-Origin"))
	}
}

func TestInvalidIDsAreRejected(t *testing.T) {
	h := &Handler{Repo: &fakeRepo{}}
	req := httptest.NewRequest(http.MethodGet, "/api/v1/jobs/nope", nil)
	rec := httptest.NewRecorder()
	h.Router().ServeHTTP(rec, req)
	if rec.Code != 400 {
		t.Fatalf("status %d", rec.Code)
	}
}

func TestTraceIDAndStructuredBodiesAreLogged(t *testing.T) {
	var logs bytes.Buffer
	logger := slog.New(slog.NewJSONHandler(&logs, nil))
	h := &Handler{Repo: &fakeRepo{}, Logger: logger}
	traceID := "00000000-0000-0000-0000-000000000042"
	req := httptest.NewRequest(http.MethodPost, "/api/v1/projects", strings.NewReader(`{"name":"demo"}`))
	req.Header.Set("X-Trace-ID", traceID)
	rec := httptest.NewRecorder()
	h.Router().ServeHTTP(rec, req)

	if got := rec.Header().Get("X-Trace-ID"); got != traceID {
		t.Fatalf("trace header %q", got)
	}
	for _, want := range []string{`"trace-id":"` + traceID + `"`, `"request_body":{"name":"demo"}`, `"response_body":`} {
		if !strings.Contains(logs.String(), want) {
			t.Fatalf("log does not contain %s: %s", want, logs.String())
		}
	}
}

func TestRequestLogsRedactSensitiveValuesNotJustFieldNames(t *testing.T) {
	var logs bytes.Buffer
	logger := slog.New(slog.NewJSONHandler(&logs, nil))
	h := &Handler{Repo: &fakeRepo{}, Logger: logger}
	req := httptest.NewRequest(http.MethodPost, "/api/v1/projects", strings.NewReader(`{"name":"https://storage.test/private/debug/object?X-Amz-Signature=secret"}`))
	rec := httptest.NewRecorder()
	h.Router().ServeHTTP(rec, req)
	if strings.Contains(logs.String(), "storage.test") || !strings.Contains(logs.String(), "[REDACTED]") {
		t.Fatalf("sensitive request text was logged: %s", logs.String())
	}
}

func TestJobValidationDoesNotPublishInvalidRequest(t *testing.T) {
	id := uuid.MustParse("00000000-0000-0000-0000-000000000001")
	repo := &fakeRepo{project: domain.Project{ID: id}, asset: domain.Asset{ID: uuid.New(), ProjectID: id, Kind: domain.AssetSource, UploadState: domain.UploadUploaded}}
	q := &fakeQueue{}
	h := &Handler{Repo: repo, Queue: q, Owner: domain.OwnerDevelopment, PipelineVersion: "p", ModelVersion: "m"}
	body := `{"source_asset_id":"` + repo.asset.ID.String() + `","target_selection":{"frame_time_ms":-1,"normalized_x":0.5,"normalized_y":0.5},"output":{"aspect_ratio":"16:9","profile":"balanced"}}`
	req := httptest.NewRequest(http.MethodPost, "/api/v1/projects/"+id.String()+"/jobs", strings.NewReader(body))
	rec := httptest.NewRecorder()
	h.Router().ServeHTTP(rec, req)
	if rec.Code != 400 || q.count != 0 {
		t.Fatalf("status %d publish count %d", rec.Code, q.count)
	}
}

func TestCompletedJobDownloadAllowsOutputWithoutFilename(t *testing.T) {
	projectID := uuid.MustParse("00000000-0000-0000-0000-000000000001")
	outputID := uuid.New()
	repo := &fakeRepo{
		project: domain.Project{ID: projectID},
		asset: domain.Asset{
			ID:          outputID,
			ProjectID:   projectID,
			Kind:        domain.AssetOutput,
			StorageKey:  "private/output/project/job.mp4",
			UploadState: domain.UploadUploaded,
		},
		job: domain.Job{
			ID:            uuid.New(),
			ProjectID:     projectID,
			State:         domain.JobCompleted,
			OutputAssetID: &outputID,
		},
	}
	h := &Handler{Repo: repo, Store: fakeStore{}, Owner: domain.OwnerDevelopment, URLTTL: time.Hour}
	req := httptest.NewRequest(http.MethodGet, "/api/v1/jobs/"+repo.job.ID.String()+"/download", nil)
	rec := httptest.NewRecorder()
	h.Router().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status %d body %s", rec.Code, rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), `"download_url":"https://download.test"`) {
		t.Fatalf("unexpected response %s", rec.Body.String())
	}
}

func evaluationManifest(reviewID uuid.UUID) []byte {
	return []byte(`{"schema_version":1,"review_id":"` + reviewID.String() + `","pipeline_version":"w0.2.0","model_version":"w0.2-ssd-mobilenetv1-12-onnx-detector-only-1","timing":{"frame_rate":60,"duration_ms":1200,"frame_count":72},"telemetry":{"status":"ready"},"phases":[{"id":"detection","status":"ready","summary":{"detected_frames":72,"detection_rate":0.9}},{"id":"framing","status":"warning","warning_intervals":[{"start_ms":3,"end_ms":7,"label":"Detection missed","detail":"The crop widened toward the full frame."}]},{"id":"render","status":"unavailable"}]}`)
}

func evaluationConfig() domain.JobConfig {
	return domain.JobConfig{PipelineVersion: "w0.2.0", ModelVersion: "w0.2-ssd-mobilenetv1-12-onnx-detector-only-1"}
}

func reviewArtifact(projectID, jobID, reviewID uuid.UUID, role, name, contentType string) domain.ReviewArtifact {
	return domain.ReviewArtifact{Role: role, Asset: domain.Asset{
		ID: uuid.New(), ProjectID: projectID, Kind: domain.AssetDebug, UploadState: domain.UploadUploaded,
		StorageKey:  "private/debug/" + projectID.String() + "/" + jobID.String() + "/" + reviewID.String() + "/" + name,
		ContentType: contentType, SizeBytes: 100,
	}}
}

func TestEvaluationRejectsMalformedAndNonterminalJobs(t *testing.T) {
	projectID, jobID := uuid.MustParse("00000000-0000-0000-0000-000000000001"), uuid.New()
	h := &Handler{Repo: &fakeRepo{project: domain.Project{ID: projectID}, job: domain.Job{ID: jobID, ProjectID: projectID, State: domain.JobUploading}}, Owner: domain.OwnerDevelopment}
	for requestURL, expectedStatus := range map[string]int{
		"/api/v1/jobs/nope/evaluation":                   http.StatusBadRequest,
		"/api/v1/jobs/" + jobID.String() + "/evaluation": http.StatusConflict,
	} {
		rec := httptest.NewRecorder()
		h.Router().ServeHTTP(rec, httptest.NewRequest(http.MethodGet, requestURL, nil))
		if rec.Code != expectedStatus {
			t.Fatalf("%s status %d: %s", requestURL, rec.Code, rec.Body.String())
		}
	}
}

func TestEvaluationRequiresOwnerAndReturnsUnavailableWithoutReview(t *testing.T) {
	projectID, jobID := uuid.MustParse("00000000-0000-0000-0000-000000000001"), uuid.New()
	repo := &fakeRepo{project: domain.Project{ID: projectID}, job: domain.Job{ID: jobID, ProjectID: projectID, State: domain.JobCompleted}, projectErr: repository.ErrNotFound}
	h := &Handler{Repo: repo, Owner: domain.OwnerDevelopment}
	rec := httptest.NewRecorder()
	h.Router().ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/v1/jobs/"+jobID.String()+"/evaluation", nil))
	if rec.Code != http.StatusNotFound {
		t.Fatalf("unauthorized status %d", rec.Code)
	}
	repo.projectErr = nil
	rec = httptest.NewRecorder()
	h.Router().ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/v1/jobs/"+jobID.String()+"/evaluation", nil))
	if rec.Code != http.StatusOK || rec.Body.String() != "{\"available\":false}\n" {
		t.Fatalf("no review response %d: %s", rec.Code, rec.Body.String())
	}
}

func TestEvaluationProjectsVerifiedPartialFailedReviewWithoutLeaks(t *testing.T) {
	projectID, jobID, reviewID := uuid.MustParse("00000000-0000-0000-0000-000000000001"), uuid.New(), uuid.New()
	artifacts := []domain.ReviewArtifact{
		reviewArtifact(projectID, jobID, reviewID, domain.ArtifactDebugManifest, "manifest.json", "application/json"),
		reviewArtifact(projectID, jobID, reviewID, domain.ArtifactDebugTelemetry, "telemetry.jsonl.gz", "application/gzip"),
		reviewArtifact(projectID, jobID, reviewID, domain.ArtifactDebugDetection, "detection.mp4", "video/mp4"),
		// Framing is manifest-declared but unavailable in persistence.
	}
	var logs bytes.Buffer
	h := &Handler{
		Repo:  &fakeRepo{project: domain.Project{ID: projectID}, job: domain.Job{ID: jobID, ProjectID: projectID, State: domain.JobFailed, Configuration: evaluationConfig()}, reviewArtifacts: artifacts},
		Store: fakeStore{manifest: evaluationManifest(reviewID), readInfo: storage.ObjectInfo{Size: 100, ContentType: "application/json"}},
		Owner: domain.OwnerDevelopment, URLTTL: time.Minute, Logger: slog.New(slog.NewJSONHandler(&logs, nil)),
	}
	rec := httptest.NewRecorder()
	h.Router().ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/v1/jobs/"+jobID.String()+"/evaluation", nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("status %d: %s", rec.Code, rec.Body.String())
	}
	body := rec.Body.String()
	for _, expected := range []string{
		`"available":true`, `"state":"failed"`, `"review_id":"` + reviewID.String(),
		`"video_url":"https://download.test"`, `"telemetry_download_url":"https://download.test"`,
		`"expires_in_seconds":60`, `"id":"framing","label":"Framing","status":"unavailable"`,
	} {
		if !strings.Contains(body, expected) {
			t.Fatalf("response missing %s: %s", expected, body)
		}
	}
	for _, forbidden := range []string{"private/debug", "manifest.json"} {
		if strings.Contains(body, forbidden) {
			t.Fatalf("response leaked %q: %s", forbidden, body)
		}
	}
	for _, secret := range []string{"private/debug", "manifest.json", string(evaluationManifest(reviewID)), "https://download.test"} {
		if strings.Contains(logs.String(), secret) {
			t.Fatalf("log leaked %q: %s", secret, logs.String())
		}
	}
}

func TestEvaluationHandlesMalformedManifestAndStorageFailure(t *testing.T) {
	projectID, jobID, reviewID := uuid.MustParse("00000000-0000-0000-0000-000000000001"), uuid.New(), uuid.New()
	artifact := reviewArtifact(projectID, jobID, reviewID, domain.ArtifactDebugManifest, "manifest.json", "application/json")
	for _, test := range []struct {
		name   string
		store  fakeStore
		status int
		media  bool
	}{
		{"malformed manifest", fakeStore{manifest: []byte("bad"), readInfo: storage.ObjectInfo{Size: 100, ContentType: "application/json"}}, http.StatusOK, false},
		{"read failure", fakeStore{readErr: errors.New("down")}, http.StatusBadGateway, false},
		{"presign failure", fakeStore{manifest: evaluationManifest(reviewID), readInfo: storage.ObjectInfo{Size: 100, ContentType: "application/json"}, presignErr: errors.New("down")}, http.StatusBadGateway, true},
	} {
		t.Run(test.name, func(t *testing.T) {
			artifacts := []domain.ReviewArtifact{artifact}
			if test.media {
				artifacts = append(artifacts, reviewArtifact(projectID, jobID, reviewID, domain.ArtifactDebugDetection, "detection.mp4", "video/mp4"))
			}
			h := &Handler{Repo: &fakeRepo{project: domain.Project{ID: projectID}, job: domain.Job{ID: jobID, ProjectID: projectID, State: domain.JobCompleted, Configuration: evaluationConfig()}, reviewArtifacts: artifacts}, Store: test.store, Owner: domain.OwnerDevelopment, URLTTL: time.Minute}
			rec := httptest.NewRecorder()
			h.Router().ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/v1/jobs/"+jobID.String()+"/evaluation", nil))
			if rec.Code != test.status {
				t.Fatalf("status %d: %s", rec.Code, rec.Body.String())
			}
			if test.status == http.StatusOK && !strings.Contains(rec.Body.String(), `"available":false`) {
				t.Fatalf("malformed manifest response: %s", rec.Body.String())
			}
		})
	}
}

func TestEvaluationRejectsSensitiveManifestWithoutLeakingIt(t *testing.T) {
	projectID, jobID, reviewID := uuid.MustParse("00000000-0000-0000-0000-000000000001"), uuid.New(), uuid.New()
	manifest := []byte(`{"schema_version":1,"review_id":"` + reviewID.String() + `","phases":[{"id":"detection","status":"unavailable","detail":"https://storage.test/private/debug?X-Amz-Signature=secret"},{"id":"framing","status":"ready"},{"id":"render","status":"ready"}]}`)
	var logs bytes.Buffer
	h := &Handler{
		Repo:  &fakeRepo{project: domain.Project{ID: projectID}, job: domain.Job{ID: jobID, ProjectID: projectID, State: domain.JobCompleted, Configuration: evaluationConfig()}, reviewArtifacts: []domain.ReviewArtifact{reviewArtifact(projectID, jobID, reviewID, domain.ArtifactDebugManifest, "manifest.json", "application/json")}},
		Store: fakeStore{manifest: manifest, readInfo: storage.ObjectInfo{Size: 100, ContentType: "application/json"}},
		Owner: domain.OwnerDevelopment, Logger: slog.New(slog.NewJSONHandler(&logs, nil)),
	}
	rec := httptest.NewRecorder()
	h.Router().ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/v1/jobs/"+jobID.String()+"/evaluation", nil))
	if rec.Code != http.StatusOK || rec.Body.String() != "{\"available\":false}\n" {
		t.Fatalf("unsafe manifest response: %d %s", rec.Code, rec.Body.String())
	}
	for _, secret := range []string{"storage.test", "X-Amz-Signature", "private/debug"} {
		if strings.Contains(logs.String(), secret) {
			t.Fatalf("log leaked %q: %s", secret, logs.String())
		}
	}
}

func TestEvaluationRejectsManifestVersionMismatchWithoutLeaks(t *testing.T) {
	projectID, jobID, reviewID := uuid.MustParse("00000000-0000-0000-0000-000000000001"), uuid.New(), uuid.New()
	manifest := bytes.Replace(evaluationManifest(reviewID), []byte(`"model_version":"w0.2-ssd-mobilenetv1-12-onnx-detector-only-1"`), []byte(`"model_version":"other-model"`), 1)
	h := &Handler{
		Repo:  &fakeRepo{project: domain.Project{ID: projectID}, job: domain.Job{ID: jobID, ProjectID: projectID, State: domain.JobCompleted, Configuration: evaluationConfig()}, reviewArtifacts: []domain.ReviewArtifact{reviewArtifact(projectID, jobID, reviewID, domain.ArtifactDebugManifest, "manifest.json", "application/json")}},
		Store: fakeStore{manifest: manifest, readInfo: storage.ObjectInfo{Size: 100, ContentType: "application/json"}},
		Owner: domain.OwnerDevelopment,
	}
	rec := httptest.NewRecorder()
	h.Router().ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/v1/jobs/"+jobID.String()+"/evaluation", nil))
	if rec.Code != http.StatusOK || rec.Body.String() != "{\"available\":false}\n" || strings.Contains(rec.Body.String(), "other-model") {
		t.Fatalf("mismatched manifest was projected: %d %s", rec.Code, rec.Body.String())
	}
}

func TestEvaluationTreatsTelemetryOnlyReviewAsVisuallyUnavailable(t *testing.T) {
	projectID, jobID, reviewID := uuid.MustParse("00000000-0000-0000-0000-000000000001"), uuid.New(), uuid.New()
	artifacts := []domain.ReviewArtifact{
		reviewArtifact(projectID, jobID, reviewID, domain.ArtifactDebugManifest, "manifest.json", "application/json"),
		reviewArtifact(projectID, jobID, reviewID, domain.ArtifactDebugTelemetry, "telemetry.jsonl.gz", "application/gzip"),
	}
	h := &Handler{
		Repo:  &fakeRepo{project: domain.Project{ID: projectID}, job: domain.Job{ID: jobID, ProjectID: projectID, State: domain.JobCompleted, Configuration: evaluationConfig()}, reviewArtifacts: artifacts},
		Store: fakeStore{manifest: evaluationManifest(reviewID), readInfo: storage.ObjectInfo{Size: 100, ContentType: "application/json"}},
		Owner: domain.OwnerDevelopment, URLTTL: time.Minute,
	}
	rec := httptest.NewRecorder()
	h.Router().ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/v1/jobs/"+jobID.String()+"/evaluation", nil))
	if rec.Code != http.StatusOK || !strings.Contains(rec.Body.String(), `"available":false`) || !strings.Contains(rec.Body.String(), `"telemetry_download_url":"https://download.test"`) || strings.Contains(rec.Body.String(), `"video_url"`) {
		t.Fatalf("telemetry-only review was not safely projected: %d %s", rec.Code, rec.Body.String())
	}
}

func TestEvaluationRejectsDuplicateOrMismatchedReviewArtifacts(t *testing.T) {
	projectID, jobID, reviewID := uuid.MustParse("00000000-0000-0000-0000-000000000001"), uuid.New(), uuid.New()
	manifest := reviewArtifact(projectID, jobID, reviewID, domain.ArtifactDebugManifest, "manifest.json", "application/json")
	for _, artifacts := range [][]domain.ReviewArtifact{
		{manifest, manifest},
		{manifest, reviewArtifact(projectID, jobID, uuid.New(), domain.ArtifactDebugDetection, "detection.mp4", "video/mp4")},
	} {
		h := &Handler{
			Repo:  &fakeRepo{project: domain.Project{ID: projectID}, job: domain.Job{ID: jobID, ProjectID: projectID, State: domain.JobCompleted, Configuration: evaluationConfig()}, reviewArtifacts: artifacts},
			Store: fakeStore{manifest: evaluationManifest(reviewID), readInfo: storage.ObjectInfo{Size: 100, ContentType: "application/json"}},
			Owner: domain.OwnerDevelopment, URLTTL: time.Minute,
		}
		rec := httptest.NewRecorder()
		h.Router().ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/v1/jobs/"+jobID.String()+"/evaluation", nil))
		if rec.Code != http.StatusOK || rec.Body.String() != "{\"available\":false}\n" {
			t.Fatalf("response did not strictly reconcile artifacts: %d %s", rec.Code, rec.Body.String())
		}
	}
}
