"""Safe command-line entrypoint for operational checks before integrations exist."""

from __future__ import annotations

import argparse
import json
import shutil
import signal
from collections.abc import Sequence

from .config import ConfigError, WorkerConfig
from .logging import configure_logging
from .runtime import RuntimeUnavailable, compose_runtime


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Boulder Frame offline worker")
    parser.add_argument(
        "--check", action="store_true", help="report configured runtime capabilities"
    )
    parser.add_argument(
        "--serve", action="store_true", help="run the worker process until it receives a signal"
    )
    parser.add_argument(
        "--config", default="/workspace/worker/conf/config.json", help="JSON configuration path"
    )
    options = parser.parse_args(arguments)
    logger = configure_logging()
    try:
        config = WorkerConfig.from_file(options.config)
    except ConfigError as error:
        parser.error(str(error))
    logger.info(
        "configuration loaded",
        extra={
            "config_path": options.config,
            "configuration": {
                "pipeline_version": config.pipeline_version,
                "model_version": config.model_version,
                "model_dir": config.model_dir,
                "scratch_root": config.scratch_root,
                "s3_bucket": config.s3_bucket,
                "s3_region": config.s3_region,
                "s3_use_path_style": config.s3_use_path_style,
                "ffmpeg_bin": config.ffmpeg_bin,
                "ffprobe_bin": config.ffprobe_bin,
                "worker_id": config.worker_id,
                "stream_name": config.stream_name,
                "stream_group": config.stream_group,
                "stream_consumer": config.stream_consumer,
                "lease_seconds": config.lease_seconds,
                "heartbeat_seconds": config.heartbeat_seconds,
                "concurrency": config.concurrency,
                "retain_debug_artifacts": config.retain_debug_artifacts,
                "debug_capture": config.debug_capture,
                "debug_visual_capture": config.debug_visual_capture,
            },
        },
    )
    capabilities = {
        "ffmpeg": shutil.which(config.ffmpeg_bin) is not None,
        "ffprobe": shutil.which(config.ffprobe_bin) is not None,
        "detector": False,
        "queue_adapter": False,
        "database_adapter": False,
        "storage_adapter": False,
    }
    runtime = None
    if options.check or options.serve:
        try:
            runtime = compose_runtime(config)
            runtime.ready()
        except (ConfigError, RuntimeUnavailable) as error:
            if options.serve:
                print(f"Worker is unavailable: {error}", flush=True)
                return 2
        else:
            capabilities.update(
                queue_adapter=runtime.capabilities.queue_adapter,
                database_adapter=runtime.capabilities.database_adapter,
                storage_adapter=runtime.capabilities.storage_adapter,
            )
    print(
        json.dumps(
            {"pipeline_version": config.pipeline_version, "capabilities": capabilities},
            sort_keys=True,
        )
    )
    logger.info(
        "worker capability response",
        extra={
            "trace_id": "unknown",
            "request_body": {"check": options.check, "serve": options.serve},
            "response_body": {
                "pipeline_version": config.pipeline_version,
                "capabilities": capabilities,
            },
            "pipeline_version": config.pipeline_version,
            "model_version": config.model_version,
        },
    )
    if options.serve:
        assert runtime is not None
        previous_handlers = {
            signal.SIGINT: signal.signal(signal.SIGINT, lambda *_: runtime.stop.set()),
            signal.SIGTERM: signal.signal(signal.SIGTERM, lambda *_: runtime.stop.set()),
        }
        try:
            runtime.serve()
        except KeyboardInterrupt:
            return 0
        finally:
            for signal_number, handler in previous_handlers.items():
                signal.signal(signal_number, handler)
            runtime.close()
    elif runtime is not None:
        runtime.close()
    if not options.check:
        print("No queue/database adapter is configured; no jobs were consumed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
