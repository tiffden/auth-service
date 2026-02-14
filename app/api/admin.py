from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.dependencies import require_role
from app.models.principal import Principal
from app.services import users_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


class UserOut(BaseModel):
    id: int
    email: str


@router.get("/users", response_model=list[UserOut])
def admin_list_users(
    principal: Annotated[Principal, Depends(require_role("admin"))],
) -> list[UserOut]:
    logger.info("Admin user list requested by user=%s", principal.user_id)
    users = users_service.list_users()
    return [UserOut(id=u.id, email=u.email) for u in users]
