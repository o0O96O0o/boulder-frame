"""Small dependency-free JSON logger for worker/queue boundary events."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        event: dict[str, Any] = {
            "module": "worker",
            "level": record.levelname.lower(),
            "message": record.getMessage(),
        }
        for key in (
            "trace_id",
            "request_body",
            "response_body",
            "job_id",
            "stage",
            "progress",
            "pipeline_version",
            "model_version",
            "duration_ms",
            "error_code",
            "diagnostic",
        ):
            if hasattr(record, key):
                output_key = "trace-id" if key == "trace_id" else key
                event[output_key] = getattr(record, key)
        if record.exc_info:
            error_type, error, _ = record.exc_info
            event["error"] = {
                "message": str(error),
                "type": error_type.__name__ if error_type is not None else "UnknownError",
            }
        return json.dumps(event, sort_keys=True, default=str)


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("boulder_frame_worker")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
