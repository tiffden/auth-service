from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.dependencies import require_user
from app.models.principal import Principal

logger = logging.getLogger(__name__)

router = APIRouter(tags=["resource"])


class ProfileOut(BaseModel):
    username: str
    message: str


@router.get("/resource/me", response_model=ProfileOut)
def get_my_profile(
    principal: Annotated[Principal, Depends(require_user)],
) -> ProfileOut:
    """Protected endpoint — requires a valid access token.

    Returns the authenticated user's identity extracted from the token.
    This demonstrates the final leg of the OAuth flow: the client uses
    the access token to reach a protected resource.
    """
    logger.info("Resource accessed by user=%s", principal.user_id)
    return ProfileOut(
        username=principal.user_id,
        message=f"Hello {principal.user_id}, you have a valid token.",
    )
