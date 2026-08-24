"""Claim/process shell with cleanup and durable state boundaries."""

from __future__ import annotations

import shutil
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import Event, Thread
from uuid import uuid4

from .config import WorkerConfig
from .debug import append_debug_record
from .errors import ErrorCode, WorkerError, terminal, transient
from .logging import configure_logging
from .protocol import JobTask
from .queue_adapter import DeliveryAction
from .state import JobRecord, JobRepository, JobState, fail, transition, utc_now

StageHandler = Callable[[JobRecord, Path], None]


@contextmanager
def job_scratch(root: Path, job_id: str, retain: bool) -> Iterator[Path]:
    path = root / job_id
    # A reclaimed delivery must reconstruct prerequisites, not reuse crash leftovers.
    shutil.rmtree(path, ignore_errors=True)
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
        publish_debug: StageHandler | None = None,
    ) -> DeliveryAction | bool:
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
            state = self.repository.current_state(task.job_id)
            self.logger.info(
                "task response",
                extra={
                    "trace_id": trace_id,
                    "response_body": {"claimed": False, "state": state.value if state else None},
                    "job_id": str(task.job_id),
                },
            )
            if state is None or state in {JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED}:
                return DeliveryAction.ACK
            return False
        if (
            record.configuration is not None
            and record.configuration.model_version != self.config.model_version
        ):
            if record.state is JobState.QUEUED:
                record = transition(record, JobState.VALIDATING, 10)
                self.repository.update(record)
            error = terminal(
                ErrorCode.MODEL_UNAVAILABLE,
                "This job requires a different model version than this worker provides.",
            )
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
            return True
        heartbeat_stop = Event()
        heartbeat_failure: list[Exception] = []

        def heartbeat() -> None:
            while not heartbeat_stop.wait(self.config.heartbeat_seconds):
                try:
                    if not self.repository.renew(
                        task.job_id, self.worker_id, self.config.lease_seconds
                    ):
                        heartbeat_failure.append(RuntimeError("job lease was lost"))
                        return
                except Exception as error:
                    heartbeat_failure.append(error)
                    return

        heartbeat_thread = Thread(target=heartbeat, name=f"lease-{task.job_id}", daemon=True)
        heartbeat_thread.start()

        def ensure_lease() -> None:
            if heartbeat_failure:
                raise transient(
                    ErrorCode.DATABASE_UNAVAILABLE,
                    "Processing was temporarily interrupted.",
                )

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
                    ensure_lease()
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
                    started = time.monotonic_ns() // 1_000_000
                    self._stage_trace(
                        scratch,
                        "stage_start",
                        {"stage": state.value, "progress": progress, "monotonic_ms": started},
                    )
                    try:
                        handler(record, scratch)
                    except Exception as error:
                        self._stage_trace(
                            scratch,
                            "stage_end",
                            {
                                "stage": state.value,
                                "progress": progress,
                                "duration_ms": (time.monotonic_ns() // 1_000_000) - started,
                                "outcome": "failed",
                                "error_code": (
                                    error.code.value
                                    if isinstance(error, WorkerError)
                                    else ErrorCode.INTERNAL.value
                                ),
                            },
                        )
                        self._publish_debug(publish_debug, record, scratch, trace_id)
                        raise
                    ensure_lease()
                    duration_ms = (time.monotonic_ns() // 1_000_000) - started
                    self._stage_trace(
                        scratch,
                        "stage_end",
                        {
                            "stage": state.value,
                            "progress": progress,
                            "duration_ms": duration_ms,
                            "outcome": "completed",
                        },
                    )
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
                            "duration_ms": duration_ms,
                        },
                    )
                self._publish_debug(publish_debug, record, scratch, trace_id)
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
                try:
                    self.repository.release(task.job_id, self.worker_id)
                except Exception:
                    # Preserve the retry classification; lease expiry remains a recovery fallback.
                    pass
                self.logger.warning(
                    "task response",
                    extra={
                        "trace_id": trace_id,
                        "response_body": {"state": "retry"},
                        "job_id": str(task.job_id),
                        "error_code": error.code.value,
                        "diagnostic": error.diagnostic,
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
                    "diagnostic": error.diagnostic,
                },
            )
        except Exception:
            try:
                self.repository.update(
                    fail(record, terminal(ErrorCode.INTERNAL, "Processing could not be completed."))
                )
            except Exception:
                self.repository.release(task.job_id, self.worker_id)
                raise
            self.logger.exception(
                "task response",
                extra={
                    "trace_id": trace_id,
                    "response_body": {"state": "failed"},
                    "job_id": str(task.job_id),
                    "error_code": ErrorCode.INTERNAL.value,
                },
            )
        finally:
            heartbeat_stop.set()
            heartbeat_thread.join()
        return True

    def _stage_trace(self, scratch: Path, record_type: str, fields: dict[str, object]) -> None:
        if self.config.debug_capture:
            try:
                append_debug_record(scratch / "debug-stages.jsonl", record_type, fields)
            except OSError:
                # Debug capture is optional and must not fail media processing.
                pass

    def _publish_debug(
        self, publish_debug: StageHandler | None, record: JobRecord, scratch: Path, trace_id: str
    ) -> None:
        if publish_debug is None or not self.config.debug_capture:
            return
        try:
            publish_debug(record, scratch)
        except Exception:
            self.logger.warning(
                "debug telemetry publish failed",
                extra={"trace_id": trace_id, "job_id": str(record.id)},
            )
