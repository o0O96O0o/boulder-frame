FROM python:3.12.10-slim-bookworm

FROM python:3.12-slim

RUN sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace/worker
COPY worker/ ./
RUN pip install --no-cache-dir -e .

CMD ["boulder-frame-worker", "--serve"]
