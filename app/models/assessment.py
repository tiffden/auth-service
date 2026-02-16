from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class Assessment:
    id: UUID
    type: str  # quiz|project|exam
    version: int = 1
    scoring_model: str = "auto"  # auto|rubric|manual
    course_id: UUID | None = None

    @staticmethod
    def new(
        *, type: str, scoring_model: str = "auto", course_id: UUID | None = None
    ) -> Assessment:
        return Assessment(
            id=uuid4(), type=type, scoring_model=scoring_model, course_id=course_id
        )


@dataclass(frozen=True, slots=True)
class AssessmentItem:
    id: UUID
    assessment_id: UUID
    kind: str  # mcq|short|code|file|peer
    prompt: str
    max_score: int
    position: int

    @staticmethod
    def new(
        *,
        assessment_id: UUID,
        kind: str,
        prompt: str,
        max_score: int,
        position: int,
    ) -> AssessmentItem:
        return AssessmentItem(
            id=uuid4(),
            assessment_id=assessment_id,
            kind=kind,
            prompt=prompt,
            max_score=max_score,
            position=position,
        )


@dataclass(frozen=True, slots=True)
class AssessmentAttempt:
    id: UUID
    assessment_id: UUID
    assessment_version: int
    user_id: UUID
    status: str = "in_progress"  # in_progress|submitted|graded|void
    started_at: int = 0
    submitted_at: int | None = None
    graded_at: int | None = None
    attempt_no: int = 1


@dataclass(frozen=True, slots=True)
class AttemptResponse:
    attempt_id: UUID
    assessment_item_id: UUID
    response_json: str
    score: int | None = None
