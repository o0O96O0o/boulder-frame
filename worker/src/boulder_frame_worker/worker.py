"""Claim/process shell with cleanup and durable state boundaries."""

from __future__ import annotations

import shutil
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from .config import WorkerConfig
from .errors import ErrorCode, WorkerError, terminal
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

    def process(
        self,
        task: JobTask,
        validating: StageHandler,
        analyzing: StageHandler,
        rendering: StageHandler,
        uploading: StageHandler,
    ) -> bool:
        record = self.repository.claim(
            task.job_id, self.worker_id, self.config.lease_seconds, utc_now()
        )
        if record is None:
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
                    handler(record, scratch)
                record = transition(record, JobState.COMPLETED, 100)
                self.repository.update(record)
        except WorkerError as error:
            if error.transient:
                raise
            self.repository.update(fail(record, error))
        except Exception:
            self.repository.update(
                fail(record, terminal(ErrorCode.INTERNAL, "Processing could not be completed."))
            )
        return True
