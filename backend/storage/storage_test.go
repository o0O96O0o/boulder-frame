package storage

import (
	"context"
	"net/url"
	"strings"
	"testing"
	"time"
)

func TestPresignUploadDoesNotSignBrowserForbiddenContentLength(t *testing.T) {
	store, err := NewS3Store(context.Background(), "http://storage.test", "http://storage.test", "us-east-1", "bucket", "key", "secret", true)
	if err != nil {
		t.Fatal(err)
	}

	uploadURL, err := store.PresignUpload(context.Background(), "source.mov", "video/quicktime", time.Minute)
	if err != nil {
		t.Fatal(err)
	}
	parsed, err := url.Parse(uploadURL)
	if err != nil {
		t.Fatal(err)
	}

	signedHeaders := parsed.Query().Get("X-Amz-SignedHeaders")
	if strings.Contains(signedHeaders, "content-length") {
		t.Fatalf("presigned upload signs browser-forbidden content-length: %q", signedHeaders)
	}
}
