from __future__ import annotations

from typing import Protocol

from app.models.oauth_client import OAuthClient


class OAuthClientRepo(Protocol):
    def get(self, client_id: str) -> OAuthClient | None: ...
    def register(self, client: OAuthClient) -> None: ...


class InMemoryOAuthClientRepo:
    def __init__(self) -> None:
        self._by_client_id: dict[str, OAuthClient] = {}

    def get(self, client_id: str) -> OAuthClient | None:
        return self._by_client_id.get(client_id)

    def register(self, client: OAuthClient) -> None:
        self._by_client_id[client.client_id] = client
