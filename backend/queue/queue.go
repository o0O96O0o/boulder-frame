package queue

import (
	"context"
	"encoding/json"
	"errors"
	"log/slog"

	"github.com/boulder-frame/backend/trace"
	"github.com/redis/go-redis/v9"
)

// These names are the language-neutral Go/Python Redis Streams contract.
const (
	// JobStream is the stream written by the Go API and read by Python.
	JobStream = "boulder-frame:jobs"
	// JobConsumerGroup is the shared Python consumer-group name.
	JobConsumerGroup = "boulder-frame:job-processors"
	TaskProcessJob   = "job.process"

	StreamFieldType    = "type"
	StreamFieldTaskID  = "task_id"
	StreamFieldPayload = "payload"
)

type Publisher interface {
	Publish(context.Context, string) error
}

type RedisStreamsPublisher struct {
	client *redis.Client
	logger *slog.Logger
}

func NewRedisStreamsPublisher(redisURL string, loggers ...*slog.Logger) (*RedisStreamsPublisher, error) {
	opt, err := redis.ParseURL(redisURL)
	if err != nil {
		return nil, err
	}
	if opt.Addr == "" {
		return nil, errors.New("redis URL must include a host")
	}
	var logger *slog.Logger
	if len(loggers) > 0 {
		logger = loggers[0]
	}
	return &RedisStreamsPublisher{client: redis.NewClient(opt), logger: logger}, nil
}

func (p *RedisStreamsPublisher) Publish(ctx context.Context, jobID string) error {
	if jobID == "" {
		return errors.New("job ID is required")
	}
	traceID := trace.ID(ctx)
	payload := struct {
		JobID   string `json:"job_id"`
		TraceID string `json:"trace_id"`
	}{JobID: jobID, TraceID: traceID}
	body, err := json.Marshal(payload)
	if err != nil {
		if p.logger != nil {
			p.logger.Error("queue response", "trace-id", traceID, "response_body", map[string]any{"accepted": false}, "error", err)
		}
		return err
	}
	if p.logger != nil {
		p.logger.Info("queue request", "trace-id", traceID, "request_body", payload)
	}
	// Redis Streams have no native task ID uniqueness. WATCH reserves a stable
	// per-job key and XADDs the entry in the same transaction, making retries
	// and concurrent API requests idempotent for this publisher.
	indexKey := JobStream + ":task:" + jobID
	var streamID string
	err = p.client.Watch(ctx, func(tx *redis.Tx) error {
		_, getErr := tx.Get(ctx, indexKey).Result()
		if getErr == nil {
			return nil
		}
		if !errors.Is(getErr, redis.Nil) {
			return getErr
		}
		commands, txErr := tx.TxPipelined(ctx, func(pipe redis.Pipeliner) error {
			streamCommand := pipe.XAdd(ctx, &redis.XAddArgs{
				Stream: JobStream,
				Values: map[string]any{
					StreamFieldType:    TaskProcessJob,
					StreamFieldTaskID:  jobID,
					StreamFieldPayload: string(body),
				},
			})
			pipe.Set(ctx, indexKey, jobID, 0)
			_ = streamCommand
			return nil
		})
		if txErr != nil {
			return txErr
		}
		if len(commands) == 0 {
			return errors.New("redis publish transaction returned no commands")
		}
		streamID, _ = commands[0].(*redis.StringCmd).Result()
		return nil
	}, indexKey)
	if p.logger != nil {
		p.logger.LogAttrs(ctx, slog.LevelInfo, "queue response", slog.String("trace-id", traceID), slog.Any("response_body", map[string]any{"accepted": err == nil, "job_id": jobID, "stream_id": streamID}))
	}
	return err
}

func (p *RedisStreamsPublisher) Close() error { return p.client.Close() }
