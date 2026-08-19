from uuid import uuid4

import pytest

from boulder_frame_worker.errors import WorkerError
from boulder_frame_worker.protocol import JobTask


def test_task_payload_preserves_trace_id() -> None:
    job_id = uuid4()
    trace_id = "00000000-0000-0000-0000-000000000042"
    task = JobTask.from_payload({"job_id": str(job_id), "trace_id": trace_id})

    assert task.job_id == job_id
    assert task.trace_id == trace_id


def test_task_payload_requires_trace_id() -> None:
    with pytest.raises(WorkerError):
        JobTask.from_payload({"job_id": str(uuid4())})
