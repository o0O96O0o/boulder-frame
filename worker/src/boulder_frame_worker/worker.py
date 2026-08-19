"""Claim/process shell with cleanup and durable state boundaries."""

from __future__ import annotations

import shutil
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from .config import WorkerConfig
from .errors import ErrorCode, WorkerError, terminal
from .logging import configure_logging
from .protocol import JobTask
from .state import JobRecord, JobRepository, JobState, fail, transition, utc_now

StageHandler = Callable[[JobRecord, Path], None]


@contextmanager
def job_scratch(root: Path, job_id: str, retain: bool) -> Iterator[Path]:
    path = root / job_id
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        if not retain:
            shutil.rmtree(path, ignore_errors=True)


class Worker:
    """Runs injected pipeline stages; database and storage adapters remain service integrations."""

    def __init__(
        self, config: WorkerConfig, repository: JobRepository, worker_id: str | None = None
    ) -> None:
        self.config = config
        self.repository = repository
        self.worker_id = worker_id or str(uuid4())
        self.logger = configure_logging()

    def process(
        self,
        task: JobTask,
        validating: StageHandler,
        analyzing: StageHandler,
        rendering: StageHandler,
        uploading: StageHandler,
    ) -> bool:
        trace_id = task.trace_id or "unknown"
        request_body = {"job_id": str(task.job_id), "trace_id": trace_id}
        self.logger.info(
            "task request",
            extra={"trace_id": trace_id, "request_body": request_body, "job_id": str(task.job_id)},
        )
        record = self.repository.claim(
            task.job_id, self.worker_id, self.config.lease_seconds, utc_now()
        )
        if record is None:
            self.logger.info(
                "task response",
                extra={
                    "trace_id": trace_id,
                    "response_body": {"claimed": False},
                    "job_id": str(task.job_id),
                },
            )
            return False
        try:
            with job_scratch(
                self.config.scratch_root, str(task.job_id), self.config.retain_debug_artifacts
            ) as scratch:
                stages = (
                    (JobState.VALIDATING, 10, validating),
                    (JobState.ANALYZING, 45, analyzing),
                    (JobState.RENDERING, 75, rendering),
                    (JobState.UPLOADING, 90, uploading),
                )
                start_at = 0
                if record.state is not JobState.QUEUED:
                    start_at = next(
                        index for index, (state, _, _) in enumerate(stages) if state is record.state
                    )
                for state, progress, handler in stages[start_at:]:
                    if record.state is not state:
                        record = transition(record, state, progress)
                        self.repository.update(record)
                    self.logger.info(
                        "stage request",
                        extra={
                            "trace_id": trace_id,
                            "request_body": {"job_id": str(task.job_id), "state": state.value},
                            "job_id": str(task.job_id),
                            "stage": state.value,
                            "progress": progress,
                            "pipeline_version": self.config.pipeline_version,
                            "model_version": self.config.model_version,
                        },
                    )
                    handler(record, scratch)
                    self.logger.info(
                        "stage response",
                        extra={
                            "trace_id": trace_id,
                            "response_body": {"state": state.value, "progress": progress},
                            "job_id": str(task.job_id),
                            "stage": state.value,
                            "progress": progress,
                            "pipeline_version": self.config.pipeline_version,
                            "model_version": self.config.model_version,
                        },
                    )
                record = transition(record, JobState.COMPLETED, 100)
                self.repository.update(record)
            self.logger.info(
                "task response",
                extra={
                    "trace_id": trace_id,
                    "response_body": {"state": "completed"},
                    "job_id": str(task.job_id),
                },
            )
        except WorkerError as error:
            if error.transient:
                self.logger.warning(
                    "task response",
                    extra={
                        "trace_id": trace_id,
                        "response_body": {"state": "retry"},
                        "job_id": str(task.job_id),
                        "error_code": error.code.value,
                    },
                )
                raise
            self.repository.update(fail(record, error))
            self.logger.info(
                "task response",
                extra={
                    "trace_id": trace_id,
                    "response_body": {"state": "failed"},
                    "job_id": str(task.job_id),
                    "error_code": error.code.value,
                },
            )
        except Exception:
            self.repository.update(
                fail(record, terminal(ErrorCode.INTERNAL, "Processing could not be completed."))
            )
            self.logger.error(
                "task response",
                extra={
                    "trace_id": trace_id,
                    "response_body": {"state": "failed"},
                    "job_id": str(task.job_id),
                    "error_code": ErrorCode.INTERNAL.value,
                },
            )
        return True
