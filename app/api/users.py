from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.auth import require_user
from app.services import users_service

logger = logging.getLogger(__name__)

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


# TODO: Is this needed?
# Create a FAKE user creation endpoint to demonstrate the PKCE flow.
# Or should it be in test code to craft up the client calls to the token endpoint
# with the right PKCE parameters?
# Let's start pulling out non-useful code from this codebase
@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def post_user(
    payload: UserCreateIn,
    _username: Annotated[str, Depends(require_user)],
) -> UserOut:
    try:
        user = users_service.create_user(email=payload.email)
        # TODO:  Mimic the following behavior from the OAuth PKCE flow:
        # I think this part will go in tests/oauth_pkce_flow_test.py,
        # which will simulate a client going through the PKCE flow against
        # the /oauth/token endpoint. The test will include steps like:
        # - Authorization Request: The client redirects the user to the
        # authorization server's login page, including the code_challenge
        # and code_challenge_method (S256) in the request.
        # - The server saves the challenge.
        # - User Authentication: The user logs in and grants permission.
        # Then off we go with the token issuance flow in /oauth/token, which verifies
        # the code_challenge and issues a token if everything is valid
        #
        # secure_transmission ():  client sends the code_challenge and
        # code_challenge_method (e.g., S256) to the authorization server
        #
        # save_challenge():  The authorization server saves the code_challenge and
        # code_challenge_method associated with the client's authorization request
        #
        # Authorization Server = oauth.py
        # Client = tests/api/test_oauth_client.py
        # PKCE logic = app/services/pkce_service.py
        # Resource Server = app/api/resource.py (or could be the same as
        # the auth server for simplicity)
    except users_service.UserAlreadyExistsError:
        logger.warning("Duplicate user rejected email=%s", payload.email)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email already exists",
        ) from None
    except users_service.UserValidationError as e:
        logger.warning("Invalid user payload: %s", e)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(e),
        ) from None

    return UserOut(id=user.id, email=user.email)
