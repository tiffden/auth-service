"""Background worker process.

RUN:  python -m app.worker

WHY A SEPARATE PROCESS?
-------------------------
The API server handles HTTP requests — it needs to be fast and
responsive.  Background tasks (credential issuance, grading) are
slow and might fail.  Running them in a separate process means:

  1. API latency stays low even when grading is CPU-heavy
  2. You can scale workers independently:
     - 3 API servers for traffic, 1 worker for grading (normal)
     - 3 API servers, 10 workers (during an exam period)
  3. A crash in the worker doesn't take down the API
  4. Workers can run on cheaper hardware (no need for low latency)

In Docker/Kubernetes, this means same image, different command:
  api:    uvicorn app.main:app --host 0.0.0.0 --port 8000
  worker: python -m app.worker

THE WORKER LOOP
----------------
This is the simplest possible worker: an infinite loop that:
  1. Polls all registered queues (round-robin)
  2. Dequeues one task at a time
  3. Dispatches to the registered handler
  4. Logs success or failure

Production systems (Celery, Dramatiq) add concurrency (multiple tasks
in parallel), retries with backoff, dead-letter queues, result backends,
and monitoring.  But the principle is identical to what you see here.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from app.services.task_queue import task_queue

TaskHandler = Callable[[dict], Coroutine[Any, Any, None]]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s  %(message)s",
)
logger = logging.getLogger("worker")


# ---------------------------------------------------------------------------
# Handler registry
# ---------------------------------------------------------------------------
# Each handler is a coroutine that processes a task payload.
# Register handlers with the @register_handler decorator.

HANDLERS: dict[str, TaskHandler] = {}


def register_handler(queue: str):
    """Decorator: register a coroutine as the handler for a queue."""

    def decorator(func):
        HANDLERS[queue] = func
        return func

    return decorator


# ---------------------------------------------------------------------------
# Task handlers
# ---------------------------------------------------------------------------


@register_handler("credential_issuance")
async def handle_credential_issuance(payload: dict) -> None:
    """Issue a credential to a user.

    In a real system, this would:
    1. Look up the credential definition from the DB
    2. Verify the user completed all requirements
    3. Create a UserCredential record
    4. Possibly call an external API (Open Badges, blockchain, etc.)
    5. Send a notification to the user
    """
    logger.info(
        "Issuing credential=%s to user=%s for course=%s",
        payload.get("credential_id"),
        payload.get("user_id"),
        payload.get("course_id"),
    )
    # Simulate work (external API call, DB writes, etc.)
    await asyncio.sleep(0.1)
    logger.info("Credential issued successfully for user=%s", payload.get("user_id"))


@register_handler("grading")
async def handle_grading(payload: dict) -> None:
    """Grade an assessment submission.

    In a real system, this would:
    1. Load the assessment rubric and the submission
    2. Run auto-grading logic (or call an AI model)
    3. Store the score in the DB
    4. Update the learner's progress projection
    5. Check if grading triggers credential issuance
    """
    logger.info("Grading submission=%s", payload.get("submission_id"))
    # Simulate heavier work
    await asyncio.sleep(0.5)
    logger.info("Grading complete for submission=%s", payload.get("submission_id"))


# ---------------------------------------------------------------------------
# Main worker loop
# ---------------------------------------------------------------------------


async def run_worker() -> None:
    """Poll all registered queues and dispatch tasks to handlers."""
    queues = list(HANDLERS.keys())
    logger.info("Worker started — listening on queues: %s", queues)

    while True:
        for queue_name in queues:
            task = await task_queue.dequeue(queue_name, timeout=1)
            if task is None:
                continue

            handler = HANDLERS[queue_name]
            try:
                await handler(task.payload)
                logger.info("Task %s on [%s] completed", task.id, queue_name)
            except Exception:
                # In production, you'd push to a dead-letter queue for
                # investigation and possible retry.  Here we just log
                # and move on.
                logger.exception("Task %s on [%s] failed", task.id, queue_name)


if __name__ == "__main__":
    asyncio.run(run_worker())
