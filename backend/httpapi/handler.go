package httpapi

import (
	"encoding/json"
	"errors"
	"log/slog"
	"mime"
	"net/http"
	"path"
	"strings"
	"time"

	"github.com/boulder-frame/backend/domain"
	"github.com/boulder-frame/backend/queue"
	"github.com/boulder-frame/backend/repository"
	"github.com/boulder-frame/backend/storage"
	"github.com/boulder-frame/backend/trace"
	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"
)

const maxEvaluationManifestBytes int64 = 256 * 1024

type Handler struct {
	Repo            repository.Repository
	Store           storage.Store
	Queue           queue.Publisher
	Owner           string
	URLTTL          time.Duration
	MaxUploadBytes  int64
	PipelineVersion string
	ModelVersion    string
	WebBaseURL      string
	Logger          *slog.Logger
}

func (h *Handler) Router() http.Handler {
	r := chi.NewRouter()
	r.Use(requestTrace)
	r.Use(h.requestLog)
	r.Use(cors(h.WebBaseURL))
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
		r.Get("/jobs/{jobID}/evaluation", h.evaluation)
		r.Get("/jobs/{jobID}/download", h.download)
	})
	return r
}

func (h *Handler) requestLog(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if h.Logger == nil {
			next.ServeHTTP(w, r)
			return
		}
		started := time.Now()
		requestBody := readRequestBody(r)
		response := &responseRecorder{ResponseWriter: w}
		next.ServeHTTP(response, r)
		if response.status == 0 {
			response.status = http.StatusOK
		}
		h.Logger.Info("http request", "trace-id", trace.ID(r.Context()), "method", r.Method, "path", r.URL.Path, "status", response.status, "duration_ms", time.Since(started).Milliseconds(), "request_body", requestBody, "response_body", sanitizeResponse(response.body.Bytes()))
	})
}

func cors(allowedOrigin string) func(http.Handler) http.Handler {
	if allowedOrigin == "" {
		allowedOrigin = "http://localhost:5173"
	}
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			origin := r.Header.Get("Origin")
			if origin == allowedOrigin {
				w.Header().Set("Access-Control-Allow-Origin", origin)
				w.Header().Set("Vary", "Origin")
				w.Header().Set("Access-Control-Allow-Headers", "Content-Type, X-Trace-ID")
				w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
			}
			if r.Method == http.MethodOptions {
				w.WriteHeader(http.StatusNoContent)
				return
			}
			next.ServeHTTP(w, r)
		})
	}
}
func requestTrace(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		id := trace.Normalize(r.Header.Get(trace.Header))
		r.Header.Set(trace.Header, id)
		w.Header().Set(trace.Header, id)
		next.ServeHTTP(w, r.WithContext(trace.WithID(r.Context(), id)))
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
		if h.Logger != nil {
			h.Logger.Error("could not create project", "trace-id", trace.ID(r.Context()), "error", err)
		}
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
		writeError(w, 400, "invalid_upload", "an MP4 or MOV file within the configured size limit is required")
		return
	}
	if !domain.ValidSourceContentType(req.Filename, req.ContentType) {
		writeError(w, 400, "invalid_upload", "content_type must be video/mp4 or video/quicktime")
		return
	}
	assetID := uuid.New()
	asset, err := h.Repo.CreateSourceAsset(r.Context(), assetID, pid, req.Filename, req.ContentType, req.SizeBytes, domain.SourceStorageKey(pid, assetID, req.Filename))
	if err != nil {
		writeError(w, 500, "internal_error", "could not create asset")
		return
	}
	url, err := h.Store.PresignUpload(r.Context(), asset.StorageKey, req.ContentType, h.URLTTL)
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
func (h *Handler) evaluation(w http.ResponseWriter, r *http.Request) {
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
	if job.State != domain.JobCompleted && job.State != domain.JobFailed {
		writeError(w, http.StatusConflict, "evaluation_unavailable", "evaluation is available only after completion or failure")
		return
	}
	artifacts, err := h.Repo.ListReviewArtifacts(r.Context(), job.ID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "internal_error", "could not load evaluation")
		return
	}
	byRole, ok := reviewArtifactsByRole(artifacts)
	if !ok {
		jsonResponse(w, http.StatusOK, domain.Evaluation{Available: false})
		return
	}
	manifestAsset, ok := byRole[domain.ArtifactDebugManifest]
	if !ok {
		jsonResponse(w, http.StatusOK, domain.Evaluation{Available: false})
		return
	}
	reviewID, ok := reviewIDForAsset(manifestAsset, job.ProjectID, job.ID, "manifest.json")
	if !ok || !jsonContentType(manifestAsset.ContentType) || manifestAsset.SizeBytes <= 0 || manifestAsset.SizeBytes > maxEvaluationManifestBytes {
		jsonResponse(w, http.StatusOK, domain.Evaluation{Available: false})
		return
	}
	manifestBytes, info, err := h.Store.Read(r.Context(), manifestAsset.StorageKey, maxEvaluationManifestBytes)
	if err != nil {
		writeError(w, http.StatusBadGateway, "storage_unavailable", "could not load evaluation")
		return
	}
	if !jsonContentType(info.ContentType) || info.Size != manifestAsset.SizeBytes {
		jsonResponse(w, http.StatusOK, domain.Evaluation{Available: false})
		return
	}
	manifest, err := domain.ParseEvaluationManifest(manifestBytes)
	if err != nil || manifest.ReviewID != reviewID || manifest.PipelineVersion != job.Configuration.PipelineVersion || manifest.ModelVersion != job.Configuration.ModelVersion {
		jsonResponse(w, http.StatusOK, domain.Evaluation{Available: false})
		return
	}
	if !validReviewArtifactSet(byRole, job.ProjectID, job.ID, reviewID) {
		jsonResponse(w, http.StatusOK, domain.Evaluation{Available: false})
		return
	}
	evaluation := domain.Evaluation{ReviewID: reviewID.String(), State: job.State, PipelineVersion: manifest.PipelineVersion, ModelVersion: manifest.ModelVersion, Timing: &manifest.Timing, ExpiresInSeconds: int(h.URLTTL / time.Second)}
	for _, phase := range manifest.Phases {
		projected := domain.EvaluationPhase{ID: phase.ID, Label: domain.ReviewPhaseLabel(phase.ID), Status: phase.Status, Detail: phase.Detail, Summary: phase.Summary, WarningIntervals: phase.WarningIntervals}
		if phase.Status == "ready" || phase.Status == "partial" || phase.Status == "warning" {
			asset, exists := byRole[domain.ReviewArtifactRoleForPhase(phase.ID)]
			if !exists || !validReviewAsset(asset, job.ProjectID, job.ID, reviewID, phase.ID+".mp4", "video/mp4") {
				projected.Status = "unavailable"
			}
		}
		evaluation.Phases = append(evaluation.Phases, projected)
	}
	for _, phase := range evaluation.Phases {
		if phase.Status != "unavailable" {
			evaluation.Available = true
			break
		}
	}
	if !evaluation.Available {
		evaluation.ReviewID = ""
		evaluation.State = ""
		evaluation.PipelineVersion = ""
		evaluation.ModelVersion = ""
		evaluation.Timing = nil
		evaluation.Phases = nil
	}
	if evaluation.Available {
		for index, phase := range evaluation.Phases {
			if phase.Status == "unavailable" {
				continue
			}
			asset := byRole[domain.ReviewArtifactRoleForPhase(phase.ID)]
			url, err := h.Store.PresignDownload(r.Context(), asset.StorageKey, h.URLTTL)
			if err != nil {
				writeError(w, http.StatusBadGateway, "storage_unavailable", "could not create evaluation URL")
				return
			}
			evaluation.Phases[index].VideoURL = url
		}
	}
	if manifest.TelemetryReady {
		if asset, exists := byRole[domain.ArtifactDebugTelemetry]; exists && validReviewAsset(asset, job.ProjectID, job.ID, reviewID, "telemetry.jsonl.gz", "application/gzip") {
			url, err := h.Store.PresignDownload(r.Context(), asset.StorageKey, h.URLTTL)
			if err != nil {
				writeError(w, http.StatusBadGateway, "storage_unavailable", "could not create evaluation URL")
				return
			}
			evaluation.TelemetryDownloadURL = url
		}
	}
	jsonResponse(w, http.StatusOK, evaluation)
}
func reviewArtifactsByRole(artifacts []domain.ReviewArtifact) (map[string]domain.Asset, bool) {
	byRole := make(map[string]domain.Asset, len(artifacts))
	for _, artifact := range artifacts {
		if !domain.ValidReviewArtifactRole(artifact.Role) {
			return nil, false
		}
		if _, exists := byRole[artifact.Role]; exists {
			return nil, false
		}
		byRole[artifact.Role] = artifact.Asset
	}
	return byRole, true
}
func validReviewArtifactSet(artifacts map[string]domain.Asset, projectID, jobID, reviewID uuid.UUID) bool {
	for role, asset := range artifacts {
		name, contentType, ok := reviewArtifactSpec(role)
		if !ok || !validReviewAsset(asset, projectID, jobID, reviewID, name, contentType) {
			return false
		}
	}
	return true
}
func reviewArtifactSpec(role string) (name, contentType string, ok bool) {
	switch role {
	case domain.ArtifactDebugTelemetry:
		return "telemetry.jsonl.gz", "application/gzip", true
	case domain.ArtifactDebugManifest:
		return "manifest.json", "application/json", true
	case domain.ArtifactDebugMeasurement:
		return "measurement.mp4", "video/mp4", true
	case domain.ArtifactDebugPose:
		return "pose.mp4", "video/mp4", true
	case domain.ArtifactDebugTracking:
		return "tracking.mp4", "video/mp4", true
	case domain.ArtifactDebugPlanning:
		return "planning.mp4", "video/mp4", true
	case domain.ArtifactDebugRender:
		return "render.mp4", "video/mp4", true
	default:
		return "", "", false
	}
}
func reviewIDForAsset(asset domain.Asset, projectID, jobID uuid.UUID, name string) (uuid.UUID, bool) {
	prefix := "private/debug/" + projectID.String() + "/" + jobID.String() + "/"
	if !strings.HasPrefix(asset.StorageKey, prefix) || path.Base(asset.StorageKey) != name {
		return uuid.Nil, false
	}
	reviewID, err := uuid.Parse(strings.TrimSuffix(strings.TrimPrefix(asset.StorageKey, prefix), "/"+name))
	if err != nil || !domain.ValidReviewStorageKey(asset.StorageKey, projectID, jobID, reviewID, name) {
		return uuid.Nil, false
	}
	return reviewID, true
}
func validReviewAsset(asset domain.Asset, projectID, jobID, reviewID uuid.UUID, name, contentType string) bool {
	return asset.UploadState == domain.UploadUploaded && asset.Kind == domain.AssetDebug && asset.SizeBytes > 0 && asset.ContentType == contentType && domain.ValidReviewStorageKey(asset.StorageKey, projectID, jobID, reviewID, name)
}
func jsonContentType(contentType string) bool {
	mediaType, _, err := mime.ParseMediaType(contentType)
	return err == nil && mediaType == "application/json"
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
