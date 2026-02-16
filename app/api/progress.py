"""Progress event ingestion and cached summary endpoint.

Implements the item completion sequence from data-model-notes-week4.md:
  Client -> POST /v1/progress/events (item_completed)
  -> append progress_event (idempotent)
  -> invalidate cache
  -> 202 Accepted

Week 6 addition: GET /v1/progress/summary/{course_id}
  -> read-through cache (check cache → miss → query store → populate → return)
"""

from __future__ import annotations

import datetime
import json
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.dependencies import require_user
from app.api.ratelimit import require_rate_limit
from app.models.principal import Principal
from app.services.cache import cache_service

router = APIRouter(prefix="/v1/progress", tags=["progress"])

# WHY 300 seconds (5 minutes): Long enough to absorb repeated dashboard
# refreshes (a learner hitting F5 to check their progress), short enough
# that stale data resolves within minutes even if explicit invalidation
# fails due to a bug.
_PROGRESS_CACHE_TTL = 300


class ProgressEventIn(BaseModel):
    course_id: str
    type: str  # enrolled|module_started|item_completed|assessment_submitted|...
    entity_type: str | None = None
    entity_id: str | None = None
    payload_json: str | None = None
    idempotency_key: str | None = None


class ProgressEventOut(BaseModel):
    id: str
    user_id: str
    course_id: str
    type: str
    occurred_at: int


# In-memory store — shared with courses.py via import if needed,
# or replaced by Postgres repos.
_PROGRESS_EVENTS: list[dict] = []


# ---------------------------------------------------------------------------
# GET /v1/progress/summary/{course_id}  — read-through cached
# ---------------------------------------------------------------------------


@router.get(
    "/summary/{course_id}",
    response_model=list[ProgressEventOut],
    dependencies=[Depends(require_rate_limit())],
)
async def get_progress_summary(
    course_id: str,
    principal: Annotated[Principal, Depends(require_user)],
) -> list[ProgressEventOut]:
    """Return all progress events for this user+course.

    This endpoint demonstrates the READ-THROUGH CACHE pattern:

    1. Build a cache key from (user_id, course_id)
    2. Check the cache for that key
    3. Cache HIT  → return cached data immediately (fast path, ~0.1ms)
    4. Cache MISS → query the data store, populate the cache, return

    The cache is invalidated (deleted) whenever a new progress event
    is ingested via POST /events, so the next GET sees fresh data.
    """
    cache_key = f"progress:{principal.user_id}:{course_id}"

    # Step 1: Try the cache
    cached = await cache_service.get(cache_key)
    if cached is not None:
        # Cache HIT — skip the data store entirely
        return [ProgressEventOut(**e) for e in json.loads(cached)]

    # Step 2: Cache MISS — compute from source of truth
    events = [
        ProgressEventOut(
            id=e["id"],
            user_id=e["user_id"],
            course_id=e["course_id"],
            type=e["type"],
            occurred_at=e["occurred_at"],
        )
        for e in _PROGRESS_EVENTS
        if e["user_id"] == principal.user_id and e["course_id"] == course_id
    ]

    # Step 3: Populate cache for next time
    await cache_service.set(
        cache_key,
        json.dumps([e.model_dump() for e in events]),
        _PROGRESS_CACHE_TTL,
    )

    return events


# ---------------------------------------------------------------------------
# POST /v1/progress/events  — ingest + invalidate cache
# ---------------------------------------------------------------------------


@router.post(
    "/events",
    response_model=ProgressEventOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_rate_limit())],
)
async def ingest_progress_event(
    event: ProgressEventIn,
    principal: Annotated[Principal, Depends(require_user)],
) -> ProgressEventOut:
    semantic_fingerprint = {
        "user_id": principal.user_id,
        "course_id": event.course_id,
        "type": event.type,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "payload_json": event.payload_json,
    }

    # Idempotency check
    if event.idempotency_key:
        for existing in _PROGRESS_EVENTS:
            if existing.get("idempotency_key") == event.idempotency_key:
                existing_fingerprint = existing.get("semantic_fingerprint")
                if (
                    existing_fingerprint is not None
                    and existing_fingerprint != semantic_fingerprint
                ):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "Idempotency key reuse with a different request payload"
                        ),
                    )
                return ProgressEventOut(**existing)

    now = int(datetime.datetime.now(datetime.UTC).timestamp())
    record = {
        "id": str(uuid4()),
        "user_id": principal.user_id,
        "course_id": event.course_id,
        "type": event.type,
        "occurred_at": now,
        "idempotency_key": event.idempotency_key,
        "semantic_fingerprint": semantic_fingerprint,
    }
    _PROGRESS_EVENTS.append(record)

    # CACHE INVALIDATION: The cached summary for this user+course is now
    # stale because we just added a new event.  Delete it so the next
    # GET /summary reads fresh data from the store.
    await cache_service.delete(f"progress:{principal.user_id}:{event.course_id}")

    return ProgressEventOut(
        id=record["id"],
        user_id=record["user_id"],
        course_id=record["course_id"],
        type=record["type"],
        occurred_at=record["occurred_at"],
    )
