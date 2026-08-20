import sys
from pathlib import Path
from types import ModuleType

import pytest

from boulder_frame_worker.config import WorkerConfig
from boulder_frame_worker.errors import ErrorCode, WorkerError
from boulder_frame_worker.storage import S3Storage


class FakeS3Client:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []
        self.failure: Exception | None = None

    def head_bucket(self, *, Bucket: str) -> None:
        self.calls.append(("head_bucket", Bucket))
        self._raise_failure()

    def download_file(self, Bucket: str, Key: str, Filename: str) -> None:
        self.calls.append(("download", (Bucket, Key, Filename)))
        self._raise_failure()
        Path(Filename).write_bytes(b"source")

    def upload_file(self, Filename: str, Bucket: str, Key: str, ExtraArgs: dict[str, str]) -> None:
        self.calls.append(("upload", (Filename, Bucket, Key, ExtraArgs)))
        self._raise_failure()

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, object]:
        self.calls.append(("head_object", (Bucket, Key)))
        self._raise_failure()
        return {"ContentLength": 42, "ContentType": "video/mp4"}

    def _raise_failure(self) -> None:
        if self.failure is not None:
            raise self.failure


def test_storage_factory_uses_configured_endpoint_and_path_style(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeConfig:
        def __init__(self, **kwargs: object) -> None:
            captured["botocore_config"] = kwargs

    def client(service_name: str, **kwargs: object) -> FakeS3Client:
        captured["service_name"] = service_name
        captured.update(kwargs)
        return FakeS3Client()

    boto3 = ModuleType("boto3")
    boto3.client = client  # type: ignore[attr-defined]
    botocore = ModuleType("botocore")
    botocore_config = ModuleType("botocore.config")
    botocore_config.Config = FakeConfig  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "boto3", boto3)
    monkeypatch.setitem(sys.modules, "botocore", botocore)
    monkeypatch.setitem(sys.modules, "botocore.config", botocore_config)
    config = WorkerConfig.from_mapping(
        {
            "s3_endpoint": "http://storage:9000",
            "s3_region": "us-east-1",
            "s3_bucket": "boulder-frame",
            "s3_access_key": "key",
            "s3_secret_key": "secret",
            "s3_use_path_style": True,
        }
    )

    storage = S3Storage.from_config(config)

    assert isinstance(storage, S3Storage)
    assert captured["service_name"] == "s3"
    assert captured["endpoint_url"] == "http://storage:9000"
    assert captured["region_name"] == "us-east-1"
    assert captured["botocore_config"] == {"s3": {"addressing_style": "path"}}


def test_storage_download_upload_and_head(tmp_path) -> None:
    client = FakeS3Client()
    storage = S3Storage(client, "bucket")
    source = tmp_path / "input.mp4"
    source.write_bytes(b"output")
    destination = tmp_path / "nested" / "source.mp4"

    storage.ready()
    storage.download("private/source/input.mp4", destination)
    uploaded = storage.upload("private/output/output.mp4", source, "video/mp4")

    assert destination.read_bytes() == b"source"
    assert uploaded.key == "private/output/output.mp4"
    assert uploaded.size_bytes == 42
    assert uploaded.content_type == "video/mp4"
    assert client.calls[2] == (
        "upload",
        (str(source), "bucket", "private/output/output.mp4", {"ContentType": "video/mp4"}),
    )
    assert client.calls[3] == ("head_object", ("bucket", "private/output/output.mp4"))


@pytest.mark.parametrize("operation", ["ready", "download", "upload", "head"])
def test_storage_classifies_service_failures_as_transient(tmp_path, operation: str) -> None:
    client = FakeS3Client()
    client.failure = OSError("service unavailable")
    storage = S3Storage(client, "bucket")
    source = tmp_path / "output.mp4"
    source.write_bytes(b"output")

    with pytest.raises(WorkerError) as error:
        if operation == "ready":
            storage.ready()
        elif operation == "download":
            storage.download("private/source/input.mp4", tmp_path / "input.mp4")
        elif operation == "upload":
            storage.upload("private/output/output.mp4", source, "video/mp4")
        else:
            storage.head("private/output/output.mp4")

    assert error.value.code is ErrorCode.STORAGE_UNAVAILABLE
    assert error.value.transient
