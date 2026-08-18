package httpapi

import (
	"context"
	"errors"
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
	project   domain.Project
	asset     domain.Asset
	job       domain.Job
	published bool
	failPing  bool
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
func (f *fakeRepo) GetJob(context.Context, uuid.UUID) (domain.Job, error) { return f.job, nil }
func (f *fakeRepo) ListArtifacts(context.Context, uuid.UUID) ([]domain.Artifact, error) {
	return []domain.Artifact{}, nil
}
func (f *fakeRepo) SetJobFailed(context.Context, uuid.UUID, string, string) error { return nil }

type fakeStore struct{}

func (fakeStore) PresignUpload(context.Context, string, string, int64, time.Duration) (string, error) {
	return "https://upload.test", nil
}
func (fakeStore) PresignDownload(context.Context, string, time.Duration) (string, error) {
	return "https://download.test", nil
}
func (fakeStore) Head(context.Context, string) (storage.ObjectInfo, error) {
	return storage.ObjectInfo{}, nil
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

func TestInvalidIDsAreRejected(t *testing.T) {
	h := &Handler{Repo: &fakeRepo{}}
	req := httptest.NewRequest(http.MethodGet, "/api/v1/jobs/nope", nil)
	rec := httptest.NewRecorder()
	h.Router().ServeHTTP(rec, req)
	if rec.Code != 400 {
		t.Fatalf("status %d", rec.Code)
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
