"""Tests for the request context middleware.

Verifies that every response gets:
- An X-Request-ID header (generated or echoed from the request)
- Request timing logged
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def test_request_id_generated_when_not_provided(client: TestClient) -> None:
    """When no X-Request-ID header is sent, one is generated."""
    resp = client.get("/health")
    req_id = resp.headers.get("x-request-id")
    assert req_id is not None
    # Should be a valid UUID
    uuid.UUID(req_id)  # raises ValueError if invalid


def test_request_id_echoed_when_provided(client: TestClient) -> None:
    """When the client sends X-Request-ID, the same value is echoed back."""
    custom_id = "my-custom-request-id-123"
    resp = client.get("/health", headers={"X-Request-ID": custom_id})
    assert resp.headers.get("x-request-id") == custom_id


def test_request_id_present_on_error_responses(client: TestClient) -> None:
    """Even error responses (401, 404) get an X-Request-ID header."""
    resp = client.get("/resource/me")  # No auth token → 401
    assert resp.headers.get("x-request-id") is not None
