"""Course and enrollment endpoints.

Implements the enrollment sequence diagram from data-model-notes-week4.md:
  Client -> POST /v1/courses/{courseId}/enroll
  -> upsert course_progress(in_progress)
  -> append progress_event(enrolled)
  -> 201 Enrolled
"""

from __future__ import annotations

import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.dependencies import require_user
from app.models.principal import Principal

router = APIRouter(prefix="/v1/courses", tags=["courses"])


class CourseOut(BaseModel):
    id: str
    slug: str
    title: str
    status: str
    version: int


class EnrollmentOut(BaseModel):
    user_id: str
    course_id: str
    status: str
    enrolled_at: int


# --- In-memory store (same pattern as existing endpoints) ---
# Will be replaced by Postgres repos when DATABASE_URL is configured.

_COURSES: dict[str, dict] = {}
_ENROLLMENTS: dict[str, dict] = {}  # key: "{user_id}:{course_id}"
_PROGRESS_EVENTS: list[dict] = []


def seed_sample_course() -> None:
    """Seed a sample course for development/testing."""
    if not _COURSES:
        _COURSES["intro-to-claude"] = {
            "id": "00000000-0000-0000-0000-000000000001",
            "slug": "intro-to-claude",
            "title": "Introduction to Claude",
            "status": "published",
            "version": 1,
        }


seed_sample_course()


@router.get("", response_model=list[CourseOut])
def list_courses(
    _principal: Annotated[Principal, Depends(require_user)],
) -> list[CourseOut]:
    return [CourseOut(**c) for c in _COURSES.values()]


@router.post(
    "/{course_id}/enroll",
    response_model=EnrollmentOut,
    status_code=status.HTTP_201_CREATED,
)
def enroll_in_course(
    course_id: str,
    principal: Annotated[Principal, Depends(require_user)],
) -> EnrollmentOut:
    if course_id not in _COURSES:
        raise HTTPException(status_code=404, detail="course not found")

    key = f"{principal.user_id}:{course_id}"
    now = int(datetime.datetime.now(datetime.UTC).timestamp())

    if key in _ENROLLMENTS:
        raise HTTPException(status_code=409, detail="already enrolled")

    _ENROLLMENTS[key] = {
        "user_id": principal.user_id,
        "course_id": course_id,
        "status": "in_progress",
        "enrolled_at": now,
    }

    _PROGRESS_EVENTS.append(
        {
            "user_id": principal.user_id,
            "course_id": course_id,
            "type": "enrolled",
            "occurred_at": now,
        }
    )

    return EnrollmentOut(**_ENROLLMENTS[key])
