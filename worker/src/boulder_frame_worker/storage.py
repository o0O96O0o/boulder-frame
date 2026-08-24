from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .config import WorkerConfig
from .errors import ErrorCode, transient


class S3Client(Protocol):
    def head_bucket(self, *, Bucket: str) -> Any: ...

    def download_file(self, Bucket: str, Key: str, Filename: str) -> None: ...

    def upload_file(
        self, Filename: str, Bucket: str, Key: str, ExtraArgs: dict[str, str]
    ) -> None: ...

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, object]: ...

    def delete_object(self, *, Bucket: str, Key: str) -> None: ...

    def get_public_access_block(self, *, Bucket: str) -> dict[str, object]: ...


@dataclass(frozen=True, slots=True)
class StoredObject:
    key: str
    size_bytes: int
    content_type: str | None


class S3Storage:
    """Minimal private-object adapter for worker source and output bytes."""

    def __init__(self, client: S3Client, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    @classmethod
    def from_config(cls, config: WorkerConfig) -> S3Storage:
        try:
            import boto3
            from botocore.config import Config
        except ImportError as error:
            raise RuntimeError("boto3 is required for S3-compatible worker storage") from error
        client = boto3.client(
            "s3",
            endpoint_url=config.s3_endpoint,
            region_name=config.s3_region,
            aws_access_key_id=config.s3_access_key,
            aws_secret_access_key=config.s3_secret_key,
            config=Config(
                s3={"addressing_style": "path" if config.s3_use_path_style else "virtual"}
            ),
        )
        return cls(client, config.s3_bucket)

    def ready(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except Exception as error:
            raise _storage_error(error) from error

    def require_private_debug_storage(self) -> None:
        """Require the bucket's S3 public-access blocks before recording athlete telemetry."""
        try:
            response = self._client.get_public_access_block(Bucket=self._bucket)
            configuration = response.get("PublicAccessBlockConfiguration")
        except Exception as error:
            raise _storage_error(error) from error
        if not isinstance(configuration, dict) or not all(
            configuration.get(name) is True
            for name in (
                "BlockPublicAcls",
                "IgnorePublicAcls",
                "BlockPublicPolicy",
                "RestrictPublicBuckets",
            )
        ):
            raise RuntimeError(
                "object storage must block public access before debug capture is enabled"
            )

    def download(self, key: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._client.download_file(self._bucket, key, str(destination))
        except Exception as error:
            raise _storage_error(error) from error

    def upload(self, key: str, source: Path, content_type: str) -> StoredObject:
        try:
            self._client.upload_file(
                str(source), self._bucket, key, ExtraArgs={"ContentType": content_type}
            )
        except Exception as error:
            raise _storage_error(error) from error
        return self.head(key)

    def head(self, key: str) -> StoredObject:
        try:
            response = self._client.head_object(Bucket=self._bucket, Key=key)
        except Exception as error:
            raise _storage_error(error) from error
        return StoredObject(
            key=key,
            size_bytes=int(response.get("ContentLength", 0)),
            content_type=_optional_string(response.get("ContentType")),
        )

    def delete(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except Exception as error:
            raise _storage_error(error) from error


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _storage_error(error: Exception) -> Exception:
    return transient(ErrorCode.STORAGE_UNAVAILABLE, "Object storage is temporarily unavailable.")
