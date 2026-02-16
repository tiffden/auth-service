"""Background task queue using Redis lists.

WHY BACKGROUND PROCESSING?
----------------------------
Some operations are too slow or too unreliable for the request/response
cycle.  If a user submits an assessment and grading takes 3 seconds,
should they stare at a spinner?  If credential issuance calls an
external API that might be down, should the request fail?

The answer is NO.  Instead:
  1. The API endpoint ENQUEUES a task (fast, <1ms) and returns
     immediately with 202 Accepted ("I got your request, I'll handle it").
  2. A separate WORKER process dequeues and processes tasks at its own
     pace, retrying on failure if needed.

This decoupling has three benefits:
  - API stays fast (no blocking on slow operations)
  - Failures are isolated (worker crash doesn't take down the API)
  - You can scale them independently (3 API servers, 1 worker — or
    10 workers during a grading surge)

THE PRODUCER/CONSUMER PATTERN
-------------------------------
  Producer (API):    LPUSH task onto a Redis list → returns immediately
  Consumer (Worker): BRPOP from the list → processes task → loops

  LPUSH adds to the HEAD of the list (left side).
  BRPOP removes from the TAIL (right side).
  HEAD-in, TAIL-out = FIFO (First In, First Out) — tasks are processed
  in the order they were enqueued.

WHY REDIS LISTS (NOT A FULL MESSAGE BROKER)?
----------------------------------------------
  Redis LPUSH/BRPOP gives us a simple, reliable FIFO queue.  It's
  already in our stack (no new infrastructure to learn, deploy, or
  monitor).  When you outgrow this — millions of tasks, guaranteed
  delivery, dead-letter queues, routing — graduate to:
    - Celery (Python task framework, uses Redis or RabbitMQ as broker)
    - Amazon SQS (managed queue service)
    - RabbitMQ (full-featured message broker with AMQP protocol)
  But start simple.  You can always add complexity later.

BRPOP vs RPOP
--------------
  RPOP returns immediately (None if empty).  A worker using RPOP in a
  loop would "busy-wait" — spinning CPU doing nothing useful.
  BRPOP BLOCKS until a task arrives (or a timeout expires).  The worker
  sleeps efficiently while waiting.  Redis internally manages the
  blocked connection with zero CPU cost.

DELIVERY GUARANTEE
-------------------
  This implementation provides AT-MOST-ONCE delivery: if the worker
  crashes mid-task, that task is lost.  For AT-LEAST-ONCE delivery,
  you'd use RPOPLPUSH (now LMOVE) to move the task to a "processing"
  list, then delete it on success.  Noted but not implemented here
  to keep things approachable.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.db.redis import redis_pool


@dataclass(frozen=True, slots=True)
class Task:
    """A unit of background work.

    id:      Unique identifier for tracking and logging.
    queue:   Which queue this task belongs to (e.g., "grading",
             "credential_issuance").  Different queues can have
             different workers with different concurrency.
    payload: Arbitrary data the handler needs (JSON-serializable).
    """

    id: str
    queue: str
    payload: dict


@runtime_checkable
class TaskQueue(Protocol):
    async def enqueue(self, queue: str, payload: dict) -> Task: ...
    async def dequeue(self, queue: str, timeout: int = 0) -> Task | None: ...
    async def queue_length(self, queue: str) -> int: ...


class InMemoryTaskQueue:
    """In-memory task queue for tests — no Redis needed."""

    def __init__(self) -> None:
        self._queues: dict[str, list[Task]] = {}

    async def enqueue(self, queue: str, payload: dict) -> Task:
        task = Task(id=str(uuid.uuid4()), queue=queue, payload=payload)
        self._queues.setdefault(queue, []).append(task)
        return task

    async def dequeue(self, queue: str, timeout: int = 0) -> Task | None:
        tasks = self._queues.get(queue, [])
        if tasks:
            return tasks.pop(0)  # FIFO: remove from front
        return None

    async def queue_length(self, queue: str) -> int:
        return len(self._queues.get(queue, []))


class RedisTaskQueue:
    """Redis-backed task queue using LPUSH/BRPOP."""

    _PREFIX = "tasks:"

    def __init__(self, redis_client) -> None:
        self._redis = redis_client

    async def enqueue(self, queue: str, payload: dict) -> Task:
        task = Task(id=str(uuid.uuid4()), queue=queue, payload=payload)
        task_json = json.dumps(
            {
                "id": task.id,
                "queue": task.queue,
                "payload": task.payload,
            }
        )
        # LPUSH: add to the LEFT (head) of the list
        # Workers BRPOP from the RIGHT (tail) → FIFO order
        await self._redis.lpush(f"{self._PREFIX}{queue}", task_json)
        return task

    async def dequeue(self, queue: str, timeout: int = 5) -> Task | None:
        # BRPOP: Blocking Right Pop — waits up to `timeout` seconds
        # for an element.  Returns None on timeout (no task available).
        result = await self._redis.brpop(f"{self._PREFIX}{queue}", timeout=timeout)
        if result is None:
            return None
        _, task_json = result
        data = json.loads(task_json)
        return Task(**data)

    async def queue_length(self, queue: str) -> int:
        return await self._redis.llen(f"{self._PREFIX}{queue}")


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

if redis_pool is not None:
    task_queue: TaskQueue = RedisTaskQueue(redis_pool)
else:
    task_queue = InMemoryTaskQueue()
