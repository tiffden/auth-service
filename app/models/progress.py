from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    """Append-only event log — the source of truth for learner progress."""

    id: UUID
    user_id: UUID
    course_id: UUID
    occurred_at: int
    type: str  # enrolled|module_started|item_completed|assessment_submitted|...
    entity_type: str | None = None
    entity_id: UUID | None = None
    payload_json: str | None = None
    idempotency_key: str | None = None

    @staticmethod
    def new(
        *,
        user_id: UUID,
        course_id: UUID,
        occurred_at: int,
        type: str,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
        payload_json: str | None = None,
        idempotency_key: str | None = None,
    ) -> ProgressEvent:
        return ProgressEvent(
            id=uuid4(),
            user_id=user_id,
            course_id=course_id,
            occurred_at=occurred_at,
            type=type,
            entity_type=entity_type,
            entity_id=entity_id,
            payload_json=payload_json,
            idempotency_key=idempotency_key,
        )


@dataclass(frozen=True, slots=True)
class CourseProgress:
    """Projection / read model — derived from progress_events.

    Like a pre-aggregated summary table. The event log is the source
    of truth; this projection makes reads fast.
    """

    user_id: UUID
    course_id: UUID
    status: str = "not_started"  # not_started|in_progress|completed
    percent_complete: int = 0
    last_activity_at: int | None = None
    completed_at: int | None = None
