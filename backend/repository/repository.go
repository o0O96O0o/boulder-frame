package repository

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"time"

	"github.com/boulder-frame/backend/domain"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

var ErrNotFound = errors.New("not found")

type Repository interface {
	Ping(context.Context) error
	CreateProject(context.Context, string, string) (domain.Project, error)
	GetProject(context.Context, uuid.UUID, string) (domain.Project, error)
	CreateSourceAsset(context.Context, uuid.UUID, uuid.UUID, string, string, int64, string) (domain.Asset, error)
	GetAsset(context.Context, uuid.UUID) (domain.Asset, error)
	MarkAssetUploaded(context.Context, uuid.UUID, int64, string) (domain.Asset, error)
	CreateOrGetJob(context.Context, domain.Job, string) (domain.Job, bool, error)
	GetJob(context.Context, uuid.UUID) (domain.Job, error)
	ListArtifacts(context.Context, uuid.UUID) ([]domain.Artifact, error)
	SetJobFailed(context.Context, uuid.UUID, string, string) error
}

type PG struct{ pool *pgxpool.Pool }

func NewPG(ctx context.Context, url string) (*PG, error) {
	pool, err := pgxpool.New(ctx, url)
	if err != nil {
		return nil, err
	}
	if err := pool.Ping(ctx); err != nil {
		pool.Close()
		return nil, err
	}
	return &PG{pool: pool}, nil
}
func (p *PG) Close()                         { p.pool.Close() }
func (p *PG) Ping(ctx context.Context) error { return p.pool.Ping(ctx) }
func (p *PG) CreateProject(ctx context.Context, name, owner string) (domain.Project, error) {
	var x domain.Project
	err := p.pool.QueryRow(ctx, `INSERT INTO projects (name, owner_id) VALUES ($1,$2) RETURNING id,name,owner_id,created_at`, name, owner).Scan(&x.ID, &x.Name, &x.OwnerID, &x.CreatedAt)
	return x, err
}
func (p *PG) GetProject(ctx context.Context, id uuid.UUID, owner string) (domain.Project, error) {
	var x domain.Project
	err := p.pool.QueryRow(ctx, `SELECT id,name,owner_id,created_at FROM projects WHERE id=$1 AND owner_id=$2`, id, owner).Scan(&x.ID, &x.Name, &x.OwnerID, &x.CreatedAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return x, ErrNotFound
	}
	return x, err
}
func (p *PG) CreateSourceAsset(ctx context.Context, id, project uuid.UUID, filename, contentType string, size int64, key string) (domain.Asset, error) {
	var x domain.Asset
	err := p.pool.QueryRow(ctx, `INSERT INTO assets (id,project_id,kind,storage_key,upload_state,filename,content_type,size_bytes) VALUES ($1,$2,'source',$3,'pending',$4,$5,$6) RETURNING id,project_id,kind,storage_key,upload_state,filename,content_type,size_bytes,created_at`, id, project, key, filename, contentType, size).Scan(&x.ID, &x.ProjectID, &x.Kind, &x.StorageKey, &x.UploadState, &x.Filename, &x.ContentType, &x.SizeBytes, &x.CreatedAt)
	return x, err
}
func (p *PG) GetAsset(ctx context.Context, id uuid.UUID) (domain.Asset, error) {
	var x domain.Asset
	err := p.pool.QueryRow(ctx, `SELECT id,project_id,kind,storage_key,upload_state,filename,content_type,size_bytes,COALESCE(width,0),COALESCE(height,0),COALESCE(frame_rate,0),COALESCE(duration_ms,0),created_at FROM assets WHERE id=$1`, id).Scan(&x.ID, &x.ProjectID, &x.Kind, &x.StorageKey, &x.UploadState, &x.Filename, &x.ContentType, &x.SizeBytes, &x.Width, &x.Height, &x.FrameRate, &x.DurationMS, &x.CreatedAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return x, ErrNotFound
	}
	return x, err
}
func (p *PG) MarkAssetUploaded(ctx context.Context, id uuid.UUID, size int64, contentType string) (domain.Asset, error) {
	var x domain.Asset
	err := p.pool.QueryRow(ctx, `UPDATE assets SET upload_state='uploaded',size_bytes=$2,content_type=COALESCE(NULLIF($3,''),content_type) WHERE id=$1 AND upload_state='pending' RETURNING id,project_id,kind,storage_key,upload_state,filename,content_type,size_bytes,created_at`, id, size, contentType).Scan(&x.ID, &x.ProjectID, &x.Kind, &x.StorageKey, &x.UploadState, &x.Filename, &x.ContentType, &x.SizeBytes, &x.CreatedAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return p.GetAsset(ctx, id)
	}
	return x, err
}
func (p *PG) CreateOrGetJob(ctx context.Context, j domain.Job, hash string) (domain.Job, bool, error) {
	b, err := json.Marshal(j.Configuration)
	if err != nil {
		return j, false, err
	}
	var x domain.Job
	var code, msg sql.NullString
	var inserted bool
	err = p.pool.QueryRow(ctx, `INSERT INTO processing_jobs (id,project_id,source_asset_id,state,stage,progress,configuration,configuration_hash) VALUES ($1,$2,$3,'queued','queued',0,$4,$5) ON CONFLICT (project_id,configuration_hash) DO UPDATE SET id=processing_jobs.id RETURNING id,project_id,source_asset_id,state,stage,progress,configuration,output_asset_id,error_code,error_message,created_at,started_at,completed_at,(xmax=0)`, j.ID, j.ProjectID, j.SourceAssetID, b, hash).Scan(&x.ID, &x.ProjectID, &x.SourceAssetID, &x.State, &x.Stage, &x.Progress, &b, &x.OutputAssetID, &code, &msg, &x.CreatedAt, &x.StartedAt, &x.CompletedAt, &inserted)
	if err != nil {
		return j, false, err
	}
	if err = json.Unmarshal(b, &x.Configuration); err != nil {
		return j, false, err
	}
	if code.Valid {
		x.Error = &domain.JobError{Code: code.String, Message: msg.String}
	}
	return x, !inserted, nil
}
func (p *PG) GetJob(ctx context.Context, id uuid.UUID) (domain.Job, error) {
	return p.queryJob(ctx, `WHERE id=$1`, id)
}
func (p *PG) queryJob(ctx context.Context, where string, args ...any) (domain.Job, error) {
	var x domain.Job
	var b []byte
	var code, msg *string
	err := p.pool.QueryRow(ctx, `SELECT id,project_id,source_asset_id,state,stage,progress,configuration,output_asset_id,error_code,error_message,created_at,started_at,completed_at FROM processing_jobs `+where, args...).Scan(&x.ID, &x.ProjectID, &x.SourceAssetID, &x.State, &x.Stage, &x.Progress, &b, &x.OutputAssetID, &code, &msg, &x.CreatedAt, &x.StartedAt, &x.CompletedAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return x, ErrNotFound
	}
	if err == nil {
		err = json.Unmarshal(b, &x.Configuration)
		if code != nil {
			x.Error = &domain.JobError{Code: *code, Message: *msg}
		}
	}
	return x, err
}
func (p *PG) ListArtifacts(ctx context.Context, id uuid.UUID) ([]domain.Artifact, error) {
	rows, err := p.pool.Query(ctx, `SELECT id,job_id,asset_id,kind,created_at FROM job_artifacts WHERE job_id=$1 ORDER BY created_at`, id)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []domain.Artifact
	for rows.Next() {
		var x domain.Artifact
		if err := rows.Scan(&x.ID, &x.JobID, &x.AssetID, &x.Kind, &x.CreatedAt); err != nil {
			return nil, err
		}
		out = append(out, x)
	}
	return out, rows.Err()
}
func (p *PG) SetJobFailed(ctx context.Context, id uuid.UUID, code, message string) error {
	_, err := p.pool.Exec(ctx, `UPDATE processing_jobs SET state='failed',stage='failed',error_code=$2,error_message=$3,completed_at=$4 WHERE id=$1`, id, code, message, time.Now().UTC())
	return err
}
