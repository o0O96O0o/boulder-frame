package queue

import (
	"context"
	"encoding/json"
	"errors"

	"github.com/hibiken/asynq"
)

const TaskProcessJob = "job.process"

type Publisher interface {
	Publish(context.Context, string) error
}
type AsynqPublisher struct{ client *asynq.Client }

func NewAsynqPublisher(redisURL string) (*AsynqPublisher, error) {
	opt, err := asynq.ParseRedisURI(redisURL)
	if err != nil {
		return nil, err
	}
	return &AsynqPublisher{client: asynq.NewClient(opt)}, nil
}
func (p *AsynqPublisher) Publish(ctx context.Context, jobID string) error {
	body, _ := json.Marshal(map[string]string{"job_id": jobID})
	_, err := p.client.EnqueueContext(ctx, asynq.NewTask(TaskProcessJob, body), asynq.TaskID(jobID), asynq.Queue("default"))
	if errors.Is(err, asynq.ErrTaskIDConflict) {
		return nil
	}
	return err
}
func (p *AsynqPublisher) Close() error { return p.client.Close() }
