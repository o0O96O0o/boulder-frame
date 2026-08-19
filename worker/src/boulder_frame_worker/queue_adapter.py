from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from enum import StrEnum
from threading import Event, Thread
from typing import Protocol
from uuid import UUID

from .errors import WorkerError
from .protocol import JobTask

TASK_PROCESS_JOB = "job.process"


class DeliveryAction(StrEnum):
    ACK = "ack"
    RETRY = "retry"


class QueueDelivery(Protocol):
    task_type: str
    task_id: str
    payload: bytes

    def ack(self) -> None: ...

    def retry(self) -> None: ...


class QueueTransport(Protocol):
    def ready(self) -> None: ...

    def serve(
        self,
        handler: Callable[[QueueDelivery], DeliveryAction],
        stop: Event,
        concurrency: int,
    ) -> None: ...

    def close(self) -> None: ...


class TaskProcessor(Protocol):
    def __call__(self, task: JobTask) -> DeliveryAction | bool: ...


class RedisStreamsClient(Protocol):
    def ping(self) -> object: ...

    def xgroup_create(self, name: str, groupname: str, id: str, mkstream: bool) -> object: ...

    def xreadgroup(
        self,
        groupname: str,
        consumername: str,
        streams: Mapping[str, str],
        count: int,
        block: int,
    ) -> object: ...

    def xautoclaim(
        self,
        name: str,
        groupname: str,
        consumername: str,
        min_idle_time: int,
        start_id: str,
        count: int,
    ) -> object: ...

    def xack(self, name: str, groupname: str, *ids: str) -> object: ...

    def xclaim(
        self,
        name: str,
        groupname: str,
        consumername: str,
        min_idle_time: int,
        message_ids: list[str],
    ) -> object: ...

    def close(self) -> object: ...


@dataclass(slots=True)
class RedisStreamDelivery:
    transport: RedisStreamsTransport
    entry_id: str
    task_type: str
    task_id: str
    payload: bytes

    def ack(self) -> None:
        self.transport.ack(self.entry_id)

    def retry(self) -> None:
        # Pending entries are deliberately retained for XAUTOCLAIM recovery.
        return None


class RedisStreamsTransport:
    """Redis Streams consumer-group transport with explicit pending recovery."""

    def __init__(
        self,
        client: RedisStreamsClient,
        stream_name: str,
        group: str,
        consumer: str,
        reclaim_idle_ms: int,
        block_ms: int,
        heartbeat_seconds: int,
    ) -> None:
        self.client = client
        self.stream_name = stream_name
        self.group = group
        self.consumer = consumer
        self.reclaim_idle_ms = reclaim_idle_ms
        self.block_ms = block_ms
        self.heartbeat_seconds = heartbeat_seconds
        self._claim_cursor = "0-0"
        self._closed = False

    def ready(self) -> None:
        self.client.ping()
        try:
            self.client.xgroup_create(self.stream_name, self.group, id="0-0", mkstream=True)
        except Exception as error:
            if "BUSYGROUP" not in str(error).upper():
                raise

    def ack(self, entry_id: str) -> None:
        self.client.xack(self.stream_name, self.group, entry_id)

    def heartbeat(self, entry_id: str) -> None:
        self.client.xclaim(
            self.stream_name,
            self.group,
            self.consumer,
            0,
            [entry_id],
        )

    def serve(
        self,
        handler: Callable[[QueueDelivery], DeliveryAction],
        stop: Event,
        concurrency: int,
    ) -> None:
        self.ready()
        active: set[Future[DeliveryAction]] = set()
        with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="redis-stream") as pool:
            while not stop.is_set() or active:
                active = {future for future in active if not future.done()}
                capacity = concurrency - len(active)
                if capacity > 0 and not stop.is_set():
                    deliveries = self._reclaim(capacity)
                    if not deliveries:
                        deliveries = self._read(capacity)
                    active.update(
                        pool.submit(self._handle, handler, delivery) for delivery in deliveries
                    )
                if active:
                    wait(active, timeout=0.05)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.client.close()

    def _reclaim(self, count: int) -> list[RedisStreamDelivery]:
        result = self.client.xautoclaim(
            self.stream_name,
            self.group,
            self.consumer,
            self.reclaim_idle_ms,
            self._claim_cursor,
            count,
        )
        if not result:
            return []
        next_id, entries, *_ = result  # redis-py returns (next_id, entries, deleted_ids).
        self._claim_cursor = _text(next_id)
        if self._claim_cursor == "0-0":
            self._claim_cursor = "0-0"
        return [_delivery(self, entry_id, fields) for entry_id, fields in entries]

    def _read(self, count: int) -> list[RedisStreamDelivery]:
        result = self.client.xreadgroup(
            self.group,
            self.consumer,
            {self.stream_name: ">"},
            count=count,
            block=self.block_ms,
        )
        if not result:
            return []
        return [
            _delivery(self, entry_id, fields)
            for _, entries in result
            for entry_id, fields in entries
        ]

    def _handle(
        self,
        handler: Callable[[QueueDelivery], DeliveryAction],
        delivery: RedisStreamDelivery,
    ) -> DeliveryAction:
        stop = Event()
        interval_seconds = self.heartbeat_seconds

        def heartbeat() -> None:
            while not stop.wait(interval_seconds):
                try:
                    self.heartbeat(delivery.entry_id)
                except Exception:
                    # The processor will retain the entry on an infrastructure failure.
                    return

        thread = Thread(target=heartbeat, name=f"stream-{delivery.entry_id}", daemon=True)
        thread.start()
        try:
            return handler(delivery)
        finally:
            stop.set()
            thread.join()


def _delivery(
    transport: RedisStreamsTransport,
    entry_id: str | bytes,
    fields: Mapping[str | bytes, str | bytes],
) -> RedisStreamDelivery:
    normalized = {_text(key): value for key, value in fields.items()}
    payload = normalized.get("payload", b"")
    return RedisStreamDelivery(
        transport=transport,
        entry_id=_text(entry_id),
        task_type=_text(normalized.get("type", "")),
        task_id=_text(normalized.get("task_id", "")),
        payload=payload.encode() if isinstance(payload, str) else payload,
    )


def _text(value: str | bytes) -> str:
    return value.decode() if isinstance(value, bytes) else value


@dataclass(slots=True)
class QueueConsumerAdapter:
    """Maps Redis Stream entries to the worker task contract."""

    transport: QueueTransport
    processor: TaskProcessor

    def ready(self) -> None:
        self.transport.ready()

    def handle(self, delivery: QueueDelivery) -> DeliveryAction:
        if delivery.task_type != TASK_PROCESS_JOB:
            delivery.ack()
            return DeliveryAction.ACK
        try:
            payload = json.loads(delivery.payload)
            task = JobTask.from_payload(payload)
            if task.job_id != UUID(delivery.task_id):
                raise ValueError("stream task ID does not match its payload")
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, WorkerError):
            delivery.ack()
            return DeliveryAction.ACK

        try:
            outcome = self.processor(task)
        except WorkerError as error:
            if error.transient:
                delivery.retry()
                return DeliveryAction.RETRY
            delivery.ack()
            return DeliveryAction.ACK
        except Exception:
            delivery.retry()
            return DeliveryAction.RETRY
        if outcome is DeliveryAction.RETRY or outcome is False:
            delivery.retry()
            return DeliveryAction.RETRY
        delivery.ack()
        return DeliveryAction.ACK

    def serve(self, stop: Event, concurrency: int) -> None:
        self.transport.serve(self.handle, stop, concurrency)

    def close(self) -> None:
        self.transport.close()
