from __future__ import annotations

from fastapi import APIRouter

# Endpoint Logic - defines GET /health

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
