"""Progress event ingestion endpoint.

Implements the item completion sequence from data-model-notes-week4.md:
  Client -> POST /v1/progress/events (item_completed)
  -> append progress_event (idempotent)
  -> 202 Accepted
"""

from __future__ import annotations

import datetime
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.dependencies import require_user
from app.models.principal import Principal

router = APIRouter(prefix="/v1/progress", tags=["progress"])


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


@router.post(
    "/events",
    response_model=ProgressEventOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def ingest_progress_event(
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

    return ProgressEventOut(
        id=record["id"],
        user_id=record["user_id"],
        course_id=record["course_id"],
        type=record["type"],
        occurred_at=record["occurred_at"],
    )
