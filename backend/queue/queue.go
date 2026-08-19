package queue

import (
	"context"
	"encoding/json"
	"errors"
	"log/slog"

	"github.com/boulder-frame/backend/trace"
	"github.com/hibiken/asynq"
)

const TaskProcessJob = "job.process"

type Publisher interface {
	Publish(context.Context, string) error
}
type AsynqPublisher struct {
	client *asynq.Client
	logger *slog.Logger
}

func NewAsynqPublisher(redisURL string, loggers ...*slog.Logger) (*AsynqPublisher, error) {
	opt, err := asynq.ParseRedisURI(redisURL)
	if err != nil {
		return nil, err
	}
	var logger *slog.Logger
	if len(loggers) > 0 {
		logger = loggers[0]
	}
	return &AsynqPublisher{client: asynq.NewClient(opt), logger: logger}, nil
}
func (p *AsynqPublisher) Publish(ctx context.Context, jobID string) error {
	traceID := trace.ID(ctx)
	payload := map[string]string{"job_id": jobID, "trace_id": traceID}
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
	_, err = p.client.EnqueueContext(ctx, asynq.NewTask(TaskProcessJob, body), asynq.TaskID(jobID), asynq.Queue("default"))
	if errors.Is(err, asynq.ErrTaskIDConflict) {
		err = nil
	}
	if p.logger != nil {
		p.logger.LogAttrs(ctx, slog.LevelInfo, "queue response", slog.String("trace-id", traceID), slog.Any("response_body", map[string]any{"accepted": err == nil, "job_id": jobID}))
	}
	return err
}
func (p *AsynqPublisher) Close() error { return p.client.Close() }
