from __future__ import annotations

from argon2 import PasswordHasher

from app.models.user import User
from app.repos.user_repo import InMemoryUserRepo
from app.services.auth_service import authenticate_user


def test_authenticate_user_rehashes_when_needed() -> None:
    # Create a user with a deliberately "weak/old" Argon2 configuration.
    old_ph = PasswordHasher(
        time_cost=1, memory_cost=8 * 1024, parallelism=1
    )  # small mem for test
    password = "pw123"
    old_hash = old_ph.hash(password)

    repo = InMemoryUserRepo()
    u = User.new(email="tee@example.com", password_hash=old_hash, roles=("user",))
    repo.add(u)

    # Authenticate using the service's hasher (default params)
    # which should decide rehash is needed
    authed = authenticate_user(repo, "tee@example.com", password)
    assert authed is not None

    # Confirm repo now stores a different (upgraded) hash
    stored = repo.get_by_email("tee@example.com")
    assert stored is not None
    assert stored.password_hash != old_hash
