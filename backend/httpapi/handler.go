package httpapi

import (
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"strings"
	"time"

	"github.com/boulder-frame/backend/domain"
	"github.com/boulder-frame/backend/queue"
	"github.com/boulder-frame/backend/repository"
	"github.com/boulder-frame/backend/storage"
	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"
)

type Handler struct {
	Repo            repository.Repository
	Store           storage.Store
	Queue           queue.Publisher
	Owner           string
	URLTTL          time.Duration
	MaxUploadBytes  int64
	PipelineVersion string
	ModelVersion    string
	Logger          *slog.Logger
}

func (h *Handler) Router() http.Handler {
	r := chi.NewRouter()
	r.Use(requestID)
	r.Use(cors)
	r.Get("/healthz", h.health)
	r.Get("/readyz", h.ready)
	r.Route("/api/v1", func(r chi.Router) {
		r.Post("/projects", h.createProject)
		r.Post("/projects/{projectID}/assets/upload", h.uploadAsset)
		r.Post("/assets/{assetID}/complete", h.completeAsset)
		r.Get("/projects/{projectID}", h.getProject)
		r.Post("/projects/{projectID}/jobs", h.createJob)
		r.Get("/jobs/{jobID}", h.getJob)
		r.Get("/jobs/{jobID}/artifacts", h.artifacts)
		r.Get("/jobs/{jobID}/download", h.download)
	})
	return r
}

func cors(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		origin := r.Header.Get("Origin")
		if origin == "http://localhost:5173" || origin == "http://127.0.0.1:5173" {
			w.Header().Set("Access-Control-Allow-Origin", origin)
			w.Header().Set("Vary", "Origin")
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type, X-Request-ID")
			w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		}
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}
func requestID(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		id := r.Header.Get("X-Request-ID")
		if id == "" {
			id = uuid.NewString()
		}
		w.Header().Set("X-Request-ID", id)
		next.ServeHTTP(w, r)
	})
}
func (h *Handler) health(w http.ResponseWriter, r *http.Request) {
	jsonResponse(w, 200, map[string]string{"status": "ok"})
}
func (h *Handler) ready(w http.ResponseWriter, r *http.Request) {
	if err := h.Repo.Ping(r.Context()); err != nil {
		jsonResponse(w, 503, map[string]string{"status": "not_ready"})
		return
	}
	jsonResponse(w, 200, map[string]string{"status": "ready"})
}

type projectRequest struct {
	Name string `json:"name"`
}

func (h *Handler) createProject(w http.ResponseWriter, r *http.Request) {
	var req projectRequest
	if !decode(r, &req) || strings.TrimSpace(req.Name) == "" {
		writeError(w, 400, "invalid_request", "name is required")
		return
	}
	x, err := h.Repo.CreateProject(r.Context(), strings.TrimSpace(req.Name), h.Owner)
	if err != nil {
		writeError(w, 500, "internal_error", "could not create project")
		return
	}
	jsonResponse(w, 201, x)
}

type uploadRequest struct {
	Filename    string `json:"filename"`
	ContentType string `json:"content_type"`
	SizeBytes   int64  `json:"size_bytes"`
}

func (h *Handler) uploadAsset(w http.ResponseWriter, r *http.Request) {
	pid, ok := parseID(w, r, "projectID")
	if !ok {
		return
	}
	if _, err := h.Repo.GetProject(r.Context(), pid, h.Owner); err != nil {
		notFound(w, err)
		return
	}
	var req uploadRequest
	if !decode(r, &req) || !domain.ValidSourceFilename(req.Filename) || req.SizeBytes <= 0 || req.SizeBytes > h.MaxUploadBytes {
		writeError(w, 400, "invalid_upload", "an MP4 file within the configured size limit is required")
		return
	}
	if req.ContentType != "video/mp4" {
		writeError(w, 400, "invalid_upload", "content_type must be video/mp4")
		return
	}
	assetID := uuid.New()
	asset, err := h.Repo.CreateSourceAsset(r.Context(), assetID, pid, req.Filename, req.ContentType, req.SizeBytes, domain.SourceStorageKey(pid, assetID, req.Filename))
	if err != nil {
		writeError(w, 500, "internal_error", "could not create asset")
		return
	}
	url, err := h.Store.PresignUpload(r.Context(), asset.StorageKey, req.ContentType, req.SizeBytes, h.URLTTL)
	if err != nil {
		writeError(w, 502, "storage_unavailable", "could not create upload URL")
		return
	}
	jsonResponse(w, 201, map[string]any{"asset": asset, "upload_url": url, "expires_in_seconds": int(h.URLTTL / time.Second)})
}
func (h *Handler) completeAsset(w http.ResponseWriter, r *http.Request) {
	id, ok := parseID(w, r, "assetID")
	if !ok {
		return
	}
	asset, err := h.Repo.GetAsset(r.Context(), id)
	if err != nil {
		notFound(w, err)
		return
	}
	if _, err := h.Repo.GetProject(r.Context(), asset.ProjectID, h.Owner); err != nil {
		notFound(w, err)
		return
	}
	if asset.UploadState == domain.UploadInvalid {
		writeError(w, 409, "invalid_state", "asset is invalid")
		return
	}
	if asset.UploadState == domain.UploadUploaded {
		jsonResponse(w, 200, asset)
		return
	}
	info, err := h.Store.Head(r.Context(), asset.StorageKey)
	if err != nil {
		writeError(w, 409, "upload_incomplete", "source object is not available")
		return
	}
	if info.Size != asset.SizeBytes {
		writeError(w, 409, "upload_size_mismatch", "uploaded object size does not match request")
		return
	}
	asset, err = h.Repo.MarkAssetUploaded(r.Context(), id, info.Size, info.ContentType)
	if err != nil {
		writeError(w, 500, "internal_error", "could not confirm upload")
		return
	}
	jsonResponse(w, 200, asset)
}
func (h *Handler) getProject(w http.ResponseWriter, r *http.Request) {
	id, ok := parseID(w, r, "projectID")
	if !ok {
		return
	}
	x, err := h.Repo.GetProject(r.Context(), id, h.Owner)
	if err != nil {
		notFound(w, err)
		return
	}
	jsonResponse(w, 200, x)
}

type jobRequest struct {
	SourceAssetID   uuid.UUID              `json:"source_asset_id"`
	TargetSelection domain.TargetSelection `json:"target_selection"`
	Output          domain.OutputSettings  `json:"output"`
}

func (h *Handler) createJob(w http.ResponseWriter, r *http.Request) {
	pid, ok := parseID(w, r, "projectID")
	if !ok {
		return
	}
	if _, err := h.Repo.GetProject(r.Context(), pid, h.Owner); err != nil {
		notFound(w, err)
		return
	}
	var req jobRequest
	if !decode(r, &req) {
		writeError(w, 400, "invalid_request", "invalid JSON")
		return
	}
	asset, err := h.Repo.GetAsset(r.Context(), req.SourceAssetID)
	if err != nil || asset.ProjectID != pid {
		notFound(w, err)
		return
	}
	if asset.Kind != domain.AssetSource || asset.UploadState != domain.UploadUploaded {
		writeError(w, 409, "asset_not_ready", "source asset must be uploaded")
		return
	}
	cfg, err := domain.NewJobConfig(asset.ID, req.TargetSelection, req.Output, h.PipelineVersion, h.ModelVersion)
	if err != nil {
		writeError(w, 400, "invalid_request", err.Error())
		return
	}
	id := uuid.New()
	job := domain.Job{ID: id, ProjectID: pid, SourceAssetID: asset.ID, State: domain.JobQueued, Stage: domain.JobQueued, Configuration: cfg, CreatedAt: time.Now().UTC()}
	hash, err := cfg.Hash()
	if err != nil {
		writeError(w, 500, "internal_error", "could not create job configuration")
		return
	}
	job, existing, err := h.Repo.CreateOrGetJob(r.Context(), job, hash)
	if err != nil {
		writeError(w, 500, "internal_error", "could not create job")
		return
	}
	if !existing || job.State == domain.JobQueued {
		if err := h.Queue.Publish(r.Context(), job.ID.String()); err != nil {
			writeError(w, 503, "queue_unavailable", "processing could not be queued")
			return
		}
	}
	jsonResponse(w, 201, job)
}
func (h *Handler) getJob(w http.ResponseWriter, r *http.Request) {
	id, ok := parseID(w, r, "jobID")
	if !ok {
		return
	}
	x, err := h.Repo.GetJob(r.Context(), id)
	if err != nil {
		notFound(w, err)
		return
	}
	if _, err := h.Repo.GetProject(r.Context(), x.ProjectID, h.Owner); err != nil {
		notFound(w, err)
		return
	}
	jsonResponse(w, 200, x)
}
func (h *Handler) artifacts(w http.ResponseWriter, r *http.Request) {
	id, ok := parseID(w, r, "jobID")
	if !ok {
		return
	}
	job, err := h.Repo.GetJob(r.Context(), id)
	if err != nil {
		notFound(w, err)
		return
	}
	if _, err := h.Repo.GetProject(r.Context(), job.ProjectID, h.Owner); err != nil {
		notFound(w, err)
		return
	}
	x, err := h.Repo.ListArtifacts(r.Context(), id)
	if err != nil {
		writeError(w, 500, "internal_error", "could not list artifacts")
		return
	}
	jsonResponse(w, 200, x)
}
func (h *Handler) download(w http.ResponseWriter, r *http.Request) {
	id, ok := parseID(w, r, "jobID")
	if !ok {
		return
	}
	job, err := h.Repo.GetJob(r.Context(), id)
	if err != nil {
		notFound(w, err)
		return
	}
	if _, err := h.Repo.GetProject(r.Context(), job.ProjectID, h.Owner); err != nil {
		notFound(w, err)
		return
	}
	if job.State != domain.JobCompleted || job.OutputAssetID == nil {
		writeError(w, 409, "output_unavailable", "job output is not available")
		return
	}
	asset, err := h.Repo.GetAsset(r.Context(), *job.OutputAssetID)
	if err != nil || asset.UploadState != domain.UploadUploaded {
		writeError(w, 409, "output_unavailable", "job output is not available")
		return
	}
	url, err := h.Store.PresignDownload(r.Context(), asset.StorageKey, h.URLTTL)
	if err != nil {
		writeError(w, 502, "storage_unavailable", "could not create download URL")
		return
	}
	jsonResponse(w, 200, map[string]any{"download_url": url, "expires_in_seconds": int(h.URLTTL / time.Second)})
}
func parseID(w http.ResponseWriter, r *http.Request, key string) (uuid.UUID, bool) {
	id, err := uuid.Parse(chi.URLParam(r, key))
	if err != nil {
		writeError(w, 400, "invalid_id", "invalid UUID")
		return uuid.Nil, false
	}
	return id, true
}
func notFound(w http.ResponseWriter, err error) {
	if errors.Is(err, repository.ErrNotFound) {
		writeError(w, 404, "not_found", "resource not found")
		return
	}
	writeError(w, 500, "internal_error", "could not load resource")
}
func decode(r *http.Request, v any) bool { return json.NewDecoder(r.Body).Decode(v) == nil }
func jsonResponse(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}
func writeError(w http.ResponseWriter, status int, code, message string) {
	jsonResponse(w, status, map[string]any{"error": map[string]string{"code": code, "message": message}})
}
