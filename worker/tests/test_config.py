import os

import pytest

from boulder_frame_worker.config import (
    LOCAL_ENV_UNCONFIGURED_MODEL_VERSION,
    UNCONFIGURED_MODEL_VERSION,
    ConfigError,
    WorkerConfig,
)


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    monkeypatch.setattr(os, "environ", {})


@pytest.fixture
def runtime_environment(monkeypatch):
    for name, value in {
        "DATABASE_URL": "postgresql://db/app",
        "REDIS_URL": "redis://redis/0",
        "S3_ENDPOINT": "http://storage:9000",
        "S3_PRESIGN_ENDPOINT": "http://storage:9000",
        "S3_REGION": "us-east-1",
        "S3_BUCKET": "boulder-frame",
        "S3_ACCESS_KEY": "key",
        "S3_SECRET_KEY": "secret",
        "WORKER_ID": "worker-1",
    }.items():
        monkeypatch.setenv(name, value)


def test_config_normalizes_local_env_unconfigured_model_sentinel(monkeypatch) -> None:
    monkeypatch.setenv("MODEL_VERSION", LOCAL_ENV_UNCONFIGURED_MODEL_VERSION)

    assert WorkerConfig.from_env().model_version == UNCONFIGURED_MODEL_VERSION


@pytest.mark.parametrize(
    "name",
    [
        "PIPELINE_VERSION",
        "MODEL_VERSION",
        "WORKER_STREAM_NAME",
        "WORKER_STREAM_GROUP",
    ],
)
def test_config_rejects_empty_identifiers(monkeypatch, name: str) -> None:
    monkeypatch.setenv(name, "   ")

    with pytest.raises(ConfigError, match=name):
        WorkerConfig.from_env()


@pytest.mark.parametrize(
    "name",
    [
        "WORKER_LEASE_SECONDS",
        "WORKER_HEARTBEAT_SECONDS",
        "WORKER_CONCURRENCY",
        "WORKER_STREAM_RECLAIM_IDLE_MS",
        "WORKER_STREAM_BLOCK_MS",
        "WORKER_DEBUG_MAX_FRAMES",
        "WORKER_DEBUG_MAX_BYTES",
        "WORKER_REVIEW_MAX_DURATION_MS",
        "WORKER_REVIEW_WIDTH",
        "WORKER_REVIEW_HEIGHT",
        "WORKER_REVIEW_MAX_BYTES",
        "WORKER_REVIEW_TIMEOUT_SECONDS",
        "WORKER_NORMALIZATION_MAX_SOURCE_BYTES",
        "WORKER_NORMALIZATION_TIMEOUT_SECONDS",
    ],
)
@pytest.mark.parametrize("value", ["0", "-1", "not-an-integer"])
def test_config_rejects_invalid_positive_integers(monkeypatch, name: str, value: str) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ConfigError, match=name):
        WorkerConfig.from_env()


@pytest.mark.parametrize(
    "name",
    [
        "S3_FORCE_PATH_STYLE",
        "WORKER_RETAIN_DEBUG_ARTIFACTS",
        "WORKER_DEBUG_CAPTURE",
        "WORKER_DEBUG_VISUAL_CAPTURE",
        "WORKER_DEBUG_REQUIRE_PRIVATE_STORAGE",
    ],
)
def test_config_rejects_invalid_boolean(monkeypatch, name: str) -> None:
    monkeypatch.setenv(name, "sometimes")

    with pytest.raises(ConfigError, match=name):
        WorkerConfig.from_env()


def test_config_keeps_debug_capture_separate_from_scratch_retention(monkeypatch) -> None:
    monkeypatch.setenv("WORKER_DEBUG_CAPTURE", "true")
    monkeypatch.setenv("WORKER_DEBUG_REQUIRE_PRIVATE_STORAGE", "false")
    config = WorkerConfig.from_env()

    assert config.debug_capture
    assert not config.debug_visual_capture
    assert not config.debug_require_private_storage
    assert not config.retain_debug_artifacts


def test_visual_capture_requires_debug_capture(monkeypatch) -> None:
    monkeypatch.setenv("WORKER_DEBUG_VISUAL_CAPTURE", "true")
    with pytest.raises(ConfigError, match="requires WORKER_DEBUG_CAPTURE"):
        WorkerConfig.from_env()

    monkeypatch.setenv("WORKER_DEBUG_CAPTURE", "true")
    assert WorkerConfig.from_env().debug_visual_capture


def test_runtime_config_requires_adapter_urls() -> None:
    with pytest.raises(ConfigError, match="database_url"):
        WorkerConfig.from_env().validate_runtime()


def test_runtime_config_requires_object_storage(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://db/app")
    monkeypatch.setenv("REDIS_URL", "redis://redis/0")

    with pytest.raises(ConfigError, match="s3_endpoint"):
        WorkerConfig.from_env().validate_runtime()


@pytest.mark.parametrize(
    "name, value, match",
    [
        ("S3_ENDPOINT", "s3://bucket", "s3_endpoint"),
        ("S3_PRESIGN_ENDPOINT", "/bucket", "s3_presign_endpoint"),
        ("DATABASE_URL", "http://db", "database_url"),
        ("REDIS_URL", "http://redis", "redis_url"),
    ],
)
def test_runtime_config_rejects_invalid_url_scheme(
    monkeypatch, runtime_environment, name: str, value: str, match: str
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ConfigError, match=match):
        WorkerConfig.from_env().validate_runtime()


def test_config_rejects_heartbeat_as_long_as_lease(monkeypatch) -> None:
    monkeypatch.setenv("WORKER_LEASE_SECONDS", "10")
    monkeypatch.setenv("WORKER_HEARTBEAT_SECONDS", "10")

    with pytest.raises(ConfigError, match="WORKER_HEARTBEAT_SECONDS"):
        WorkerConfig.from_env()


def test_runtime_config_requires_worker_id_and_defaults_consumer_to_it(
    monkeypatch, runtime_environment
) -> None:
    monkeypatch.delenv("WORKER_ID")
    with pytest.raises(ConfigError, match="worker_id"):
        WorkerConfig.from_env().validate_runtime()

    monkeypatch.setenv("WORKER_ID", "worker-1")
    config = WorkerConfig.from_env()
    config.validate_runtime()
    assert config.stream_consumer == "worker-1"


def test_reclaim_timing_tracks_lease_unless_explicitly_configured(
    monkeypatch, runtime_environment
) -> None:
    monkeypatch.setenv("WORKER_LEASE_SECONDS", "600")
    config = WorkerConfig.from_env()
    config.validate_runtime()
    assert config.stream_reclaim_idle_ms == 600_000

    monkeypatch.setenv("WORKER_STREAM_RECLAIM_IDLE_MS", "599999")
    with pytest.raises(ConfigError, match="stream_reclaim_idle_ms"):
        WorkerConfig.from_env().validate_runtime()


def test_environment_credentials_are_literal(monkeypatch, runtime_environment) -> None:
    secret = 'quoted"value\\with\n${OTHER_SECRET}'
    monkeypatch.setenv("S3_SECRET_KEY", secret)
    monkeypatch.setenv("OTHER_SECRET", "must-not-expand")

    config = WorkerConfig.from_env()
    config.validate_runtime()
    assert config.s3_secret_key == secret
