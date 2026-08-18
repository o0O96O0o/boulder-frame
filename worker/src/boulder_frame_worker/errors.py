"""User-safe worker failures and retry classification."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ErrorCode(StrEnum):
    INVALID_TASK = "invalid_task"
    INVALID_MEDIA = "invalid_media"
    UNSUPPORTED_CONTAINER = "unsupported_container"
    UNSUPPORTED_VIDEO_CODEC = "unsupported_video_codec"
    UNSUPPORTED_AUDIO_CODEC = "unsupported_audio_codec"
    VARIABLE_FRAME_RATE = "variable_frame_rate"
    MISSING_VIDEO_STREAM = "missing_video_stream"
    INVALID_TARGET_SELECTION = "invalid_target_selection"
    NO_SELECTED_ATHLETE = "no_selected_athlete"
    MODEL_UNAVAILABLE = "model_unavailable"
    RENDER_UNAVAILABLE = "render_unavailable"
    INVALID_OUTPUT = "invalid_output"
    STORAGE_UNAVAILABLE = "storage_unavailable"
    DATABASE_UNAVAILABLE = "database_unavailable"
    INTERNAL = "internal"


@dataclass(slots=True)
class WorkerError(Exception):
    """A failure suitable for durable job storage without exposing internals."""

    code: ErrorCode
    message: str
    transient: bool = False

    def __str__(self) -> str:
        return self.message


def terminal(code: ErrorCode, message: str) -> WorkerError:
    return WorkerError(code=code, message=message, transient=False)


def transient(code: ErrorCode, message: str) -> WorkerError:
    return WorkerError(code=code, message=message, transient=True)
