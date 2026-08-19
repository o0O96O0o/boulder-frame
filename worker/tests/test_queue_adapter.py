import json
from dataclasses import dataclass
from threading import Event
from uuid import uuid4

import pytest

from boulder_frame_worker.errors import ErrorCode, transient
from boulder_frame_worker.queue_adapter import (
    DeliveryAction,
    QueueConsumerAdapter,
    RedisStreamsTransport,
)


@dataclass
class FakeDelivery:
    task_type: str
    task_id: str
    payload: bytes
    acknowledged: bool = False
    retried: bool = False

    def ack(self) -> None:
        self.acknowledged = True

    def retry(self) -> None:
        self.retried = True


class FakeTransport:
    def __init__(self) -> None:
        self.closed = False
        self.ready_called = False

    def ready(self) -> None:
        self.ready_called = True

    def serve(self, handler, stop: Event, concurrency: int) -> None:
        assert concurrency == 2

    def close(self) -> None:
        self.closed = True


class FakeRedis:
    def __init__(self) -> None:
        self.group_creates = 0
        self.claims: list[object] = []
        self.reads: list[object] = []
        self.acks: list[tuple[str, str, tuple[str, ...]]] = []
        self.claim_heartbeats: list[tuple[str, str, str, int, list[str]]] = []
        self.closed = False

    def ping(self) -> bool:
        return True

    def xgroup_create(self, name, groupname, id, mkstream):
        self.group_creates += 1
        return True

    def xreadgroup(self, groupname, consumername, streams, count, block):
        assert streams == {"jobs": ">"}
        return self.reads.pop(0) if self.reads else []

    def xautoclaim(self, name, groupname, consumername, min_idle_time, start_id, count):
        return self.claims.pop(0) if self.claims else ("0-0", [], [])

    def xack(self, name, groupname, *ids):
        self.acks.append((name, groupname, ids))
        return len(ids)

    def xclaim(self, name, groupname, consumername, min_idle_time, message_ids):
        self.claim_heartbeats.append((name, groupname, consumername, min_idle_time, message_ids))
        return []

    def close(self) -> None:
        self.closed = True


def task_payload(job_id: str) -> bytes:
    return json.dumps(
        {"job_id": job_id, "trace_id": "00000000-0000-0000-0000-000000000042"}
    ).encode()


def test_queue_adapter_acknowledges_valid_task() -> None:
    seen = []
    job_id = str(uuid4())
    delivery = FakeDelivery("job.process", job_id, task_payload(job_id))
    adapter = QueueConsumerAdapter(FakeTransport(), lambda task: seen.append(task))

    assert adapter.handle(delivery) is DeliveryAction.ACK
    assert delivery.acknowledged
    assert not delivery.retried
    assert len(seen) == 1


def test_queue_adapter_acknowledges_malformed_unknown_or_mismatched_task() -> None:
    job_id = str(uuid4())
    malformed = FakeDelivery("job.process", job_id, b"not-json")
    unknown = FakeDelivery("other", job_id, b"not-json")
    mismatch = FakeDelivery("job.process", str(uuid4()), task_payload(job_id))
    adapter = QueueConsumerAdapter(FakeTransport(), lambda task: pytest.fail("not called"))

    assert adapter.handle(malformed) is DeliveryAction.ACK
    assert adapter.handle(unknown) is DeliveryAction.ACK
    assert adapter.handle(mismatch) is DeliveryAction.ACK
    assert malformed.acknowledged and unknown.acknowledged and mismatch.acknowledged


def test_queue_adapter_leaves_transient_processor_error_pending() -> None:
    job_id = str(uuid4())
    delivery = FakeDelivery("job.process", job_id, task_payload(job_id))

    def process(task):
        raise transient(ErrorCode.DATABASE_UNAVAILABLE, "database unavailable")

    adapter = QueueConsumerAdapter(FakeTransport(), process)

    assert adapter.handle(delivery) is DeliveryAction.RETRY
    assert delivery.retried
    assert not delivery.acknowledged


def test_redis_stream_transport_preserves_contract_and_reclaims_pending_entry() -> None:
    redis = FakeRedis()
    job_id = str(uuid4())
    payload = task_payload(job_id)
    redis.claims.append(
        (
            "0-0",
            [("1710000000000-0", {"type": "job.process", "task_id": job_id, "payload": payload})],
            [],
        )
    )
    transport = RedisStreamsTransport(redis, "jobs", "workers", "worker-1", 100, 1, 1)

    transport.ready()
    delivery = transport._reclaim(1)[0]

    assert delivery.task_type == "job.process"
    assert delivery.task_id == job_id
    assert delivery.payload == payload
    delivery.ack()
    assert redis.acks == [("jobs", "workers", ("1710000000000-0",))]
    transport.heartbeat(delivery.entry_id)
    assert redis.claim_heartbeats == [("jobs", "workers", "worker-1", 0, ["1710000000000-0"])]


def test_queue_adapter_keeps_unclaimed_job_pending() -> None:
    job_id = str(uuid4())
    delivery = FakeDelivery("job.process", job_id, task_payload(job_id))
    adapter = QueueConsumerAdapter(FakeTransport(), lambda task: False)

    assert adapter.handle(delivery) is DeliveryAction.RETRY
    assert delivery.retried
    assert not delivery.acknowledged


def test_queue_adapter_delegates_serve_ready_and_close() -> None:
    transport = FakeTransport()
    adapter = QueueConsumerAdapter(transport, lambda task: True)

    adapter.ready()
    adapter.serve(Event(), 2)
    adapter.close()

    assert transport.ready_called
    assert transport.closed
