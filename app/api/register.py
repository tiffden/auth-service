"""JSON auth endpoints for SPA clients (/auth/register, /auth/login).

Both return { accessToken, user: { id, email, name } } so the client
can store the token in memory and navigate to /dashboard immediately.
"""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.login import user_repo
from app.models.user import User
from app.services import auth_service, token_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# --- Request / Response schemas -------------------------------------------


class LoginIn(BaseModel):
    email: str
    password: str


class RegisterIn(BaseModel):
    name: str
    email: str
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    name: str


class AuthResponse(BaseModel):
    accessToken: str
    refreshToken: str
    user: UserOut


# --- POST /auth/login -----------------------------------------------------


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginIn) -> AuthResponse:
    email = payload.email.lower().strip()

    user = auth_service.authenticate_user(user_repo, email, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Invalid email or password"},
        )

    logger.info("Login succeeded  user_id=%s email=%s", user.id, email)

    access_token = token_service.create_access_token(
        sub=str(user.id),
        roles=list(user.roles) or ["user"],
    )
    refresh_token = token_service.create_refresh_token(sub=str(user.id))

    return AuthResponse(
        accessToken=access_token,
        refreshToken=refresh_token,
        user=UserOut(id=str(user.id), email=user.email, name=user.name),
    )


# --- POST /auth/register --------------------------------------------------


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(payload: RegisterIn) -> AuthResponse:
    email = payload.email.lower().strip()
    name = payload.name.strip()

    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Invalid email address"},
        )

    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Name is required"},
        )

    if len(payload.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Password must be at least 8 characters"},
        )

    # Check for existing user
    if user_repo.get_by_email(email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "A user with this email already exists"},
        )

    # Create user
    password_hash = auth_service.hash_password(payload.password)
    user = User.new(email=email, password_hash=password_hash, name=name)

    try:
        user_repo.add(user)
    except ValueError:
        # Race condition — another request created the same email
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "A user with this email already exists"},
        ) from None

    logger.info("User registered  user_id=%s email=%s", user.id, email)

    # Issue access + refresh tokens
    access_token = token_service.create_access_token(
        sub=str(user.id),
        roles=list(user.roles) or ["user"],
    )
    refresh_token = token_service.create_refresh_token(sub=str(user.id))

    return AuthResponse(
        accessToken=access_token,
        refreshToken=refresh_token,
        user=UserOut(id=str(user.id), email=user.email, name=user.name),
    )
