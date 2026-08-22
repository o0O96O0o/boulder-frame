FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.10.9 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*


WORKDIR /workspace/worker
COPY worker/pyproject.toml worker/uv.lock ./

RUN uv sync --locked --no-dev --no-install-project
COPY worker/ ./

RUN uv sync --locked --no-dev

CMD ["boulder-frame-worker", "--serve"]
