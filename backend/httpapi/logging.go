package httpapi

import (
	"bytes"
	"encoding/json"
	"io"
	"mime"
	"net/http"
	"strings"
)

const maxLoggedBodyBytes = 64 * 1024

type responseRecorder struct {
	http.ResponseWriter
	status int
	body   bytes.Buffer
}

func (r *responseRecorder) WriteHeader(status int) {
	if r.status != 0 {
		return
	}
	r.status = status
	r.ResponseWriter.WriteHeader(status)
}

func (r *responseRecorder) Write(body []byte) (int, error) {
	if r.status == 0 {
		r.WriteHeader(http.StatusOK)
	}
	if r.body.Len() < maxLoggedBodyBytes {
		remaining := maxLoggedBodyBytes - r.body.Len()
		logged := body
		if len(logged) > remaining {
			logged = logged[:remaining]
		}
		_, _ = r.body.Write(logged)
	}
	return r.ResponseWriter.Write(body)
}

func readRequestBody(r *http.Request) any {
	if r.Body == nil {
		return nil
	}
	contentType, _, _ := mime.ParseMediaType(r.Header.Get("Content-Type"))
	if contentType != "" && !strings.HasPrefix(contentType, "application/json") {
		return map[string]any{"omitted": true, "content_type": contentType}
	}
	original := r.Body
	body, err := io.ReadAll(io.LimitReader(original, maxLoggedBodyBytes+1))
	r.Body = io.NopCloser(io.MultiReader(bytes.NewReader(body), original))
	if err != nil {
		return map[string]any{"omitted": true, "reason": "read_error"}
	}
	// Keep the complete stream available to the handler without reading it into memory here.
	return sanitizeBody(body)
}

func sanitizeBody(body []byte) any {
	if len(body) == 0 {
		return nil
	}
	if len(body) > maxLoggedBodyBytes {
		return map[string]any{"omitted": true, "reason": "body_too_large"}
	}
	var value any
	if json.Unmarshal(body, &value) == nil {
		return sanitizeValue(value)
	}
	return map[string]any{"omitted": true, "reason": "non_json_body"}
}

func sanitizeResponse(body []byte) any { return sanitizeBody(body) }

func sanitizeValue(value any) any {
	switch value := value.(type) {
	case map[string]any:
		out := make(map[string]any, len(value))
		for key, item := range value {
			if sensitiveLogKey(key) {
				out[key] = "[REDACTED]"
				continue
			}
			out[key] = sanitizeValue(item)
		}
		return out
	case string:
		if sensitiveLogText(value) {
			return "[REDACTED]"
		}
		return value
	case []any:
		out := make([]any, len(value))
		for index, item := range value {
			out[index] = sanitizeValue(item)
		}
		return out
	default:
		return value
	}
}

func sensitiveLogKey(key string) bool {
	key = strings.NewReplacer("_", "", "-", "", ".", "").Replace(strings.ToLower(key))
	return strings.Contains(key, "url") || strings.Contains(key, "uri") || strings.Contains(key, "href") ||
		strings.Contains(key, "token") || strings.Contains(key, "secret") || strings.Contains(key, "password") ||
		strings.Contains(key, "authorization") || strings.Contains(key, "cookie") || strings.Contains(key, "credential") ||
		strings.Contains(key, "signature") || strings.Contains(key, "accesskey") || strings.Contains(key, "storagekey") ||
		strings.Contains(key, "objectkey") || strings.Contains(key, "endpoint")
}

func sensitiveLogText(value string) bool {
	lower := strings.ToLower(value)
	return strings.Contains(lower, "://") || strings.Contains(lower, "www.") || strings.Contains(lower, "x-amz-") ||
		strings.Contains(lower, "private/debug/") || strings.Contains(lower, "access_key") || strings.Contains(lower, "secret") ||
		strings.Contains(lower, "token") || strings.Contains(lower, "password") || strings.Contains(lower, "authorization") ||
		strings.Contains(lower, "credential") || strings.Contains(lower, "signature")
}
