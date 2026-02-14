from __future__ import annotations

import dataclasses
import datetime
from typing import Protocol

from app.models.authorization_code import AuthorizationCode


class AuthCodeRepo(Protocol):
    def create(self, record: AuthorizationCode) -> None: ...
    def get_by_code_hash(self, code_hash: str) -> AuthorizationCode | None: ...
    def mark_used(self, code_hash: str) -> AuthorizationCode | None: ...


class InMemoryAuthCodeRepo:
    def __init__(self) -> None:
        self._by_code_hash: dict[str, AuthorizationCode] = {}

    def create(self, record: AuthorizationCode) -> None:
        self._by_code_hash[record.code_hash] = record

    def get_by_code_hash(self, code_hash: str) -> AuthorizationCode | None:
        return self._by_code_hash.get(code_hash)

    def mark_used(self, code_hash: str) -> AuthorizationCode | None:
        """Atomically mark a code as used. Returns the updated record, or None
        if the code doesn't exist or was already consumed."""
        record = self._by_code_hash.get(code_hash)
        if record is None:
            return None
        if record.used_at is not None:
            return None
        updated = dataclasses.replace(
            record, used_at=int(datetime.datetime.now(datetime.UTC).timestamp())
        )
        self._by_code_hash[code_hash] = updated
        return updated
