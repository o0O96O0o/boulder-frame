FROM golang:1.25-alpine

RUN apk add --no-cache curl

WORKDIR /workspace/backend
COPY backend/go.mod backend/go.sum ./

RUN go mod download
COPY backend/ ./
COPY deploy/docker/backend-entrypoint.sh /usr/local/bin/backend-entrypoint

RUN chmod +x /usr/local/bin/backend-entrypoint

EXPOSE 8080

ENTRYPOINT ["/usr/local/bin/backend-entrypoint"]
