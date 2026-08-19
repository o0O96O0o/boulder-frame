FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace/worker
COPY worker/ ./
RUN pip install --no-cache-dir -e .

CMD ["boulder-frame-worker", "--serve"]
