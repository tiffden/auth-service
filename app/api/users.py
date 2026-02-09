from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.auth import require_user
from app.services import users_service

router = APIRouter(tags=["users"])


class UserOut(BaseModel):
    id: int
    email: str


@router.get("/users", response_model=list[UserOut])
def get_users(_username: Annotated[str, Depends(require_user)]) -> list[UserOut]:
    users = users_service.list_users()
    return [UserOut(id=u.id, email=u.email) for u in users]
