from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class Course:
    id: UUID
    slug: str
    title: str
    status: str = "draft"  # draft|published|retired
    version: int = 1
    created_by: UUID | None = None
    org_id: UUID | None = None

    @staticmethod
    def new(
        *,
        slug: str,
        title: str,
        created_by: UUID | None = None,
        org_id: UUID | None = None,
    ) -> Course:
        return Course(
            id=uuid4(), slug=slug, title=title, created_by=created_by, org_id=org_id
        )


@dataclass(frozen=True, slots=True)
class CourseModule:
    id: UUID
    course_id: UUID
    position: int
    title: str

    @staticmethod
    def new(*, course_id: UUID, position: int, title: str) -> CourseModule:
        return CourseModule(
            id=uuid4(), course_id=course_id, position=position, title=title
        )


@dataclass(frozen=True, slots=True)
class ModuleItem:
    id: UUID
    module_id: UUID
    type: str  # lesson|assessment|external
    position: int
    ref_id: UUID | None = None

    @staticmethod
    def new(
        *, module_id: UUID, type: str, position: int, ref_id: UUID | None = None
    ) -> ModuleItem:
        return ModuleItem(
            id=uuid4(), module_id=module_id, type=type, position=position, ref_id=ref_id
        )


@dataclass(frozen=True, slots=True)
class LearningPathway:
    id: UUID
    slug: str
    title: str
    status: str = "draft"
    version: int = 1

    @staticmethod
    def new(*, slug: str, title: str) -> LearningPathway:
        return LearningPathway(id=uuid4(), slug=slug, title=title)


@dataclass(frozen=True, slots=True)
class PathwayCourse:
    pathway_id: UUID
    course_id: UUID
    position: int
