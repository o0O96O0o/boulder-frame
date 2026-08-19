"""Safe command-line entrypoint for operational checks before integrations exist."""

from __future__ import annotations

import argparse
import json
import shutil
import time
from collections.abc import Sequence

from .config import ConfigError, WorkerConfig
from .logging import configure_logging


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
    capabilities = {
        "ffmpeg": shutil.which(config.ffmpeg_bin) is not None,
        "ffprobe": shutil.which(config.ffprobe_bin) is not None,
        "detector": False,
        "pose_estimator": False,
        "queue_adapter": False,
        "database_adapter": False,
    }
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
        print("Queue/database adapter is not configured; worker is idle.", flush=True)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            return 0
    if not options.check:
        print("No queue/database adapter is configured; no jobs were consumed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
