import pytest

from boulder_frame_worker.config import ConfigError, WorkerConfig


def test_config_uses_safe_defaults() -> None:
    config = WorkerConfig.from_mapping({})

    assert config.pipeline_version == "development"
    assert config.model_version == "unconfigured"
    assert config.lease_seconds == 300
    assert not config.retain_debug_artifacts


@pytest.mark.parametrize("value", ["0", "-1", "nope"])
def test_config_rejects_invalid_lease(value: str) -> None:
    with pytest.raises(ConfigError, match="lease_seconds"):
        WorkerConfig.from_mapping({"lease_seconds": value})


def test_config_rejects_invalid_boolean() -> None:
    with pytest.raises(ConfigError, match="retain_debug_artifacts"):
        WorkerConfig.from_mapping({"retain_debug_artifacts": "sometimes"})
