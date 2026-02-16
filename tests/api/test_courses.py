"""Tests for course listing and enrollment endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

# ---- 401: unauthenticated ----


def test_list_courses_rejects_missing_token(client: TestClient) -> None:
    resp = client.get("/v1/courses")
    assert resp.status_code == 401


def test_enroll_rejects_missing_token(client: TestClient) -> None:
    resp = client.post("/v1/courses/intro-to-claude/enroll")
    assert resp.status_code == 401


# ---- 200: list courses ----


def test_list_courses_returns_seeded_course(client: TestClient, token: str) -> None:
    resp = client.get("/v1/courses", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    courses = resp.json()
    assert len(courses) >= 1
    slugs = [c["slug"] for c in courses]
    assert "intro-to-claude" in slugs


# ---- 201: enrollment ----


def test_enroll_success(client: TestClient, token: str) -> None:
    resp = client.post(
        "/v1/courses/intro-to-claude/enroll",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["course_id"] == "intro-to-claude"
    assert body["status"] == "in_progress"
    assert "enrolled_at" in body


# ---- 404: course not found ----


def test_enroll_course_not_found(client: TestClient, token: str) -> None:
    resp = client.post(
        "/v1/courses/nonexistent/enroll",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
