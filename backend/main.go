package main

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"sort"
	"strings"
	"syscall"
	"time"

	"github.com/boulder-frame/backend/config"
	"github.com/boulder-frame/backend/httpapi"
	"github.com/boulder-frame/backend/queue"
	"github.com/boulder-frame/backend/repository"
	"github.com/boulder-frame/backend/storage"
	"github.com/jackc/pgx/v5/pgxpool"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	cfg, err := config.Load(configPath(os.Args[1:]))
	if err != nil {
		logger.Error("invalid configuration", "error", err)
		os.Exit(1)
	}
	if hasArgument(os.Args[1:], "migrate") && hasArgument(os.Args[1:], "up") {
		if err := migrate(context.Background(), cfg.DatabaseURL); err != nil {
			logger.Error("migration failed", "error", err)
			os.Exit(1)
		}
		return
	}
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()
	repo, err := repository.NewPG(ctx, cfg.DatabaseURL)
	if err != nil {
		logger.Error("database unavailable", "error", err)
		os.Exit(1)
	}
	defer repo.Close()
	store, err := storage.NewS3Store(ctx, cfg.S3Endpoint, cfg.S3PresignEndpoint, cfg.S3Region, cfg.S3Bucket, cfg.S3AccessKey, cfg.S3SecretKey, cfg.S3UsePathStyle)
	if err != nil {
		logger.Error("storage unavailable", "error", err)
		os.Exit(1)
	}
	publisher, err := queue.NewRedisStreamsPublisher(cfg.RedisURL, logger)
	if err != nil {
		logger.Error("redis configuration invalid", "error", err)
		os.Exit(1)
	}
	defer publisher.Close()
	h := &httpapi.Handler{Repo: repo, Store: store, Queue: publisher, Owner: cfg.DevelopmentOwner, URLTTL: cfg.URLTTL, MaxUploadBytes: cfg.MaxUploadBytes, PipelineVersion: cfg.PipelineVersion, ModelVersion: cfg.ModelVersion, Logger: logger}
	server := &http.Server{Addr: cfg.HTTPAddr, Handler: h.Router(), ReadHeaderTimeout: 10 * time.Second, ReadTimeout: 30 * time.Second, WriteTimeout: 30 * time.Second, IdleTimeout: 60 * time.Second}
	go func() {
		logger.Info("api listening", "addr", cfg.HTTPAddr)
		if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			logger.Error("http server stopped", "error", err)
			stop()
		}
	}()
	<-ctx.Done()
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := server.Shutdown(shutdownCtx); err != nil {
		logger.Error("graceful shutdown failed", "error", err)
		os.Exit(1)
	}
}

func configPath(args []string) string {
	for index, arg := range args {
		if arg == "--config" && index+1 < len(args) {
			return args[index+1]
		}
		if len(arg) > len("--config=") && arg[:len("--config=")] == "--config=" {
			return arg[len("--config="):]
		}
	}
	return ""
}

func hasArgument(args []string, expected string) bool {
	for _, arg := range args {
		if arg == expected {
			return true
		}
	}
	return false
}

func migrate(ctx context.Context, databaseURL string) error {
	paths, err := migrationPaths("migrations")
	if err != nil {
		return err
	}
	pool, err := pgxpool.New(ctx, databaseURL)
	if err != nil {
		return err
	}
	defer pool.Close()
	if err := pool.Ping(ctx); err != nil {
		return err
	}
	_, err = pool.Exec(ctx, `CREATE TABLE IF NOT EXISTS schema_migrations (
		version text PRIMARY KEY,
		applied_at timestamptz NOT NULL DEFAULT now()
	)`)
	if err != nil {
		return err
	}
	for _, path := range paths {
		if err := applyMigration(ctx, pool, path); err != nil {
			return err
		}
	}
	return nil
}

func migrationPaths(dir string) ([]string, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, err
	}
	paths := make([]string, 0, len(entries))
	for _, entry := range entries {
		if entry.IsDir() || !strings.HasSuffix(entry.Name(), ".sql") {
			continue
		}
		paths = append(paths, filepath.Join(dir, entry.Name()))
	}
	sort.Strings(paths)
	return paths, nil
}

func applyMigration(ctx context.Context, pool *pgxpool.Pool, path string) error {
	sqlBytes, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	version := filepath.Base(path)
	tx, err := pool.Begin(ctx)
	if err != nil {
		return err
	}
	defer tx.Rollback(ctx)
	if _, err := tx.Exec(ctx, `SELECT pg_advisory_xact_lock(hashtextextended('boulder-frame-schema-migrations', 0))`); err != nil {
		return err
	}
	var applied bool
	if err := tx.QueryRow(ctx, `SELECT EXISTS (SELECT 1 FROM schema_migrations WHERE version=$1)`, version).Scan(&applied); err != nil {
		return err
	}
	if applied {
		return tx.Commit(ctx)
	}
	if _, err := tx.Exec(ctx, string(sqlBytes)); err != nil {
		return err
	}
	if _, err := tx.Exec(ctx, `INSERT INTO schema_migrations (version) VALUES ($1)`, version); err != nil {
		return err
	}
	return tx.Commit(ctx)
}
