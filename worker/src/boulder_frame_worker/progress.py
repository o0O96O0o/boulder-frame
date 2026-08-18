"""Structured, monotonic job progress records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .state import JobStage


@dataclass(frozen=True, slots=True)
class ProgressUpdate:
    stage: JobStage
    percent: int
    recorded_at: datetime
    elapsed_ms: int | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.percent <= 100:
            raise ValueError("progress must be between 0 and 100")
        if self.elapsed_ms is not None and self.elapsed_ms < 0:
            raise ValueError("elapsed_ms must not be negative")
