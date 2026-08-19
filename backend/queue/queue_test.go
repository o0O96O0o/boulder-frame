package queue

import (
	"context"
	"encoding/json"
	"errors"
	"net"
	"os/exec"
	"strconv"
	"testing"
	"time"

	"github.com/boulder-frame/backend/trace"
	"github.com/redis/go-redis/v9"
)

func TestRedisStreamsPublisherPublishesContractAndIsIdempotent(t *testing.T) {
	addr, stop := startRedis(t)
	defer stop()
	publisher, err := NewRedisStreamsPublisher("redis://" + addr)
	if err != nil {
		t.Fatal(err)
	}
	defer publisher.Close()

	ctx := trace.WithID(context.Background(), "trace-42")
	if err := publisher.Publish(ctx, "job-42"); err != nil {
		t.Fatal(err)
	}
	if err := publisher.Publish(ctx, "job-42"); err != nil {
		t.Fatal(err)
	}

	client := redis.NewClient(&redis.Options{Addr: addr})
	defer client.Close()
	entries, err := client.XRange(context.Background(), JobStream, "-", "+").Result()
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 1 {
		t.Fatalf("stream entries = %d, want 1", len(entries))
	}
	entry := entries[0]
	if got, want := entry.Values[StreamFieldType], TaskProcessJob; got != want {
		t.Fatalf("type = %v, want %v", got, want)
	}
	if got, want := entry.Values[StreamFieldTaskID], "job-42"; got != want {
		t.Fatalf("task_id = %v, want %v", got, want)
	}
	var payload map[string]string
	if err := json.Unmarshal([]byte(entry.Values[StreamFieldPayload].(string)), &payload); err != nil {
		t.Fatal(err)
	}
	if len(payload) != 2 || payload["job_id"] != "job-42" || payload["trace_id"] != "trace-42" {
		t.Fatalf("payload = %#v, want exactly job_id and trace_id", payload)
	}
}

func TestRedisStreamsPublisherValidatesURLAndJobID(t *testing.T) {
	if _, err := NewRedisStreamsPublisher("not-a-redis-url"); err == nil {
		t.Fatal("invalid Redis URL accepted")
	}
	addr, stop := startRedis(t)
	defer stop()
	publisher, err := NewRedisStreamsPublisher("redis://" + addr)
	if err != nil {
		t.Fatal(err)
	}
	defer publisher.Close()
	if err := publisher.Publish(context.Background(), ""); err == nil {
		t.Fatal("empty job ID accepted")
	}
}

func TestRedisStreamsPublisherHonorsCanceledContext(t *testing.T) {
	addr, stop := startRedis(t)
	defer stop()
	publisher, err := NewRedisStreamsPublisher("redis://" + addr)
	if err != nil {
		t.Fatal(err)
	}
	defer publisher.Close()
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if err := publisher.Publish(ctx, "job-canceled"); !errors.Is(err, context.Canceled) {
		t.Fatalf("Publish error = %v, want context.Canceled", err)
	}
}

func startRedis(t *testing.T) (string, func()) {
	t.Helper()
	if _, err := exec.LookPath("redis-server"); err != nil {
		t.Skip("redis-server is not installed")
	}
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	addr := listener.Addr().String()
	port := strconv.Itoa(listener.Addr().(*net.TCPAddr).Port)
	if err := listener.Close(); err != nil {
		t.Fatal(err)
	}
	cmd := exec.Command("redis-server", "--bind", "127.0.0.1", "--port", port, "--save", "", "--appendonly", "no")
	if err := cmd.Start(); err != nil {
		t.Fatal(err)
	}
	client := redis.NewClient(&redis.Options{Addr: addr})
	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		if err := client.Ping(context.Background()).Err(); err == nil {
			client.Close()
			return addr, func() {
				_ = cmd.Process.Kill()
				_ = cmd.Wait()
			}
		}
		time.Sleep(25 * time.Millisecond)
	}
	client.Close()
	_ = cmd.Process.Kill()
	_ = cmd.Wait()
	t.Fatal("redis-server did not become ready")
	return "", nil
}
