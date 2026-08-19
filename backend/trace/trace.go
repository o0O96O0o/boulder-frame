package trace

import (
	"context"

	"github.com/google/uuid"
)

const Header = "X-Trace-ID"

type contextKey struct{}

func New() string { return uuid.NewString() }

func Normalize(value string) string {
	if id, err := uuid.Parse(value); err == nil {
		return id.String()
	}
	return New()
}

func WithID(ctx context.Context, id string) context.Context {
	return context.WithValue(ctx, contextKey{}, id)
}

func ID(ctx context.Context) string {
	if id, ok := ctx.Value(contextKey{}).(string); ok && id != "" {
		return id
	}
	return New()
}
