import pytest

from boulder_frame_worker.config import (
    LOCAL_ENV_UNCONFIGURED_MODEL_VERSION,
    UNCONFIGURED_MODEL_VERSION,
    ConfigError,
    WorkerConfig,
)
from boulder_frame_worker.models import MODEL_VERSION


def test_config_uses_safe_defaults() -> None:
    config = WorkerConfig.from_mapping({})

    assert config.pipeline_version == "development"
    assert config.model_version == UNCONFIGURED_MODEL_VERSION
    assert config.lease_seconds == 300
    assert not config.retain_debug_artifacts


def test_config_normalizes_local_env_unconfigured_model_sentinel() -> None:
    config = WorkerConfig.from_mapping({"model_version": LOCAL_ENV_UNCONFIGURED_MODEL_VERSION})

    assert config.model_version == UNCONFIGURED_MODEL_VERSION


def test_config_preserves_explicit_baseline_model_configuration(tmp_path) -> None:
    config = WorkerConfig.from_mapping(
        {"model_version": MODEL_VERSION, "model_dir": str(tmp_path / "models")}
    )

    assert config.model_version == MODEL_VERSION
    assert config.model_dir == tmp_path / "models"


@pytest.mark.parametrize("value", ["0", "-1", "nope"])
def test_config_rejects_invalid_lease(value: str) -> None:
    with pytest.raises(ConfigError, match="lease_seconds"):
        WorkerConfig.from_mapping({"lease_seconds": value})


def test_config_rejects_invalid_boolean() -> None:
    with pytest.raises(ConfigError, match="retain_debug_artifacts"):
        WorkerConfig.from_mapping({"retain_debug_artifacts": "sometimes"})


def test_runtime_config_requires_adapter_urls() -> None:
    with pytest.raises(ConfigError, match="database_url"):
        WorkerConfig.from_mapping({}).validate_runtime()


def test_runtime_config_requires_object_storage() -> None:
    config = WorkerConfig.from_mapping(
        {"database_url": "postgresql://db/app", "redis_url": "redis://redis/0"}
    )

    with pytest.raises(ConfigError, match="s3_endpoint"):
        config.validate_runtime()


def test_runtime_config_rejects_invalid_s3_url() -> None:
    config = WorkerConfig.from_mapping({**_runtime_values(), "s3_endpoint": "s3://bucket"})

    with pytest.raises(ConfigError, match="s3_endpoint"):
        config.validate_runtime()


def test_config_rejects_heartbeat_longer_than_lease() -> None:
    with pytest.raises(ConfigError, match="heartbeat_seconds"):
        WorkerConfig.from_mapping({"lease_seconds": 10, "heartbeat_seconds": 10})


def test_runtime_config_rejects_invalid_url_scheme() -> None:
    config = WorkerConfig.from_mapping({**_runtime_values(), "database_url": "http://db"})
    with pytest.raises(ConfigError, match="database_url"):
        config.validate_runtime()


def test_runtime_config_requires_worker_id_and_defaults_consumer_to_it() -> None:
    config = WorkerConfig.from_mapping(_runtime_values())
    with pytest.raises(ConfigError, match="worker_id"):
        config.validate_runtime()

    config = WorkerConfig.from_mapping({**_runtime_values(), "worker_id": "worker-1"})
    config.validate_runtime()
    assert config.stream_consumer == "worker-1"


@pytest.mark.parametrize(
    "values, match",
    [
        ({"stream_reclaim_idle_ms": 299_999}, "stream_reclaim_idle_ms"),
    ],
)
def test_runtime_config_requires_safe_stream_lease_timing(values, match: str) -> None:
    config = WorkerConfig.from_mapping({**_runtime_values(), "worker_id": "worker-1", **values})

    with pytest.raises(ConfigError, match=match):
        config.validate_runtime()


def _runtime_values() -> dict[str, object]:
    return {
        "database_url": "postgresql://db/app",
        "redis_url": "redis://redis/0",
        "s3_endpoint": "http://storage:9000",
        "s3_presign_endpoint": "http://storage:9000",
        "s3_region": "us-east-1",
        "s3_bucket": "boulder-frame",
        "s3_access_key": "key",
        "s3_secret_key": "secret",
    }
