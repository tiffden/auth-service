from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.auth import require_user
from app.services import users_service

# Endpoint Logic - defines GET /users and POST /users
# Delegates to users_service.list_users()

router = APIRouter(tags=["users"])


class UserOut(BaseModel):
    id: int
    email: str


class UserCreateIn(BaseModel):
    email: str


@router.get("/users", response_model=list[UserOut])
def get_users(_username: Annotated[str, Depends(require_user)]) -> list[UserOut]:
    users = users_service.list_users()
    return [UserOut(id=u.id, email=u.email) for u in users]


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def post_user(
    payload: UserCreateIn,
    _username: Annotated[str, Depends(require_user)],
) -> UserOut:
    try:
        user = users_service.create_user(email=payload.email)
    except users_service.UserAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email already exists",
        ) from None
    except users_service.UserValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(e),
        ) from None

    return UserOut(id=user.id, email=user.email)
