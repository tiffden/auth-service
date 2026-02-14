from __future__ import annotations

import logging

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError

from app.models.user import User

# from app.repos.auth_code_repo import AuthCodeRepo
# from app.repos.oauth_client_repo import OAuthClientRepo
from app.repos.user_repo import UserRepo

# Tunable; defaults are generally reasonable. You can pin parameters later.
# Argon2 hash strings encode parameters + salt
logger = logging.getLogger(__name__)

_ph = PasswordHasher()


def hash_password(plain_password: str) -> str:
    if not plain_password:
        raise ValueError("password must be non-empty")
    # Argon2 includes salt+params in the returned encoded string.
    return _ph.hash(plain_password)


# verify_password() must catch Argon2 exceptions and return False
def verify_password(plain_password: str, password_hash: str) -> bool:
    if not plain_password or not password_hash:
        return False
    try:
        return _ph.verify(password_hash, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHash):
        return False


def authenticate_user(repo: UserRepo, email: str, password: str) -> User | None:
    user = repo.get_by_email(email)
    if user is None:
        return None
    if not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None

    # Optional: upgrade stored hash if parameters changed over time.
    # This is a “nice later” feature; safe to include now.
    try:
        if _ph.check_needs_rehash(user.password_hash):
            new_hash = _ph.hash(password)
            repo.update_password_hash(user.id, new_hash)
            logger.info("Rehashed password for user=%s", user.id)
    except InvalidHash:
        # If it's not a valid argon2 hash, treat as non-auth (already handled above),
        # but don't blow up.
        return None

    return user
