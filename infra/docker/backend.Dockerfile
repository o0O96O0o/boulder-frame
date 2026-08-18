FROM golang:1.24.1-alpine3.21

FROM golang:1.25-alpine

RUN apk add --no-cache curl

WORKDIR /workspace/backend
COPY backend/go.mod backend/go.sum ./
RUN go mod download
COPY backend/ ./
COPY infra/docker/backend-entrypoint.sh /usr/local/bin/backend-entrypoint
RUN chmod +x /usr/local/bin/backend-entrypoint

EXPOSE 8080

ENTRYPOINT ["/usr/local/bin/backend-entrypoint"]
