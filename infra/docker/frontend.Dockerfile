FROM node:22.14.0-alpine3.21

FROM node:22-alpine

RUN apk add --no-cache busybox-extras

WORKDIR /workspace/frontend
COPY frontend/ ./

EXPOSE 5173

CMD ["/bin/sh", "-ec", "npm install && npm run dev -- --host 0.0.0.0 --port 5173"]
