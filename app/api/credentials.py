"""Credential verification and issuance endpoints.

Implements the credential issuance flow from data-model-notes-week4.md.
- GET  /v1/credentials/{id}/verify — public verification endpoint
- POST /v1/credentials/issue        — enqueue credential issuance (Week 6)

Week 6 addition: The issue endpoint demonstrates the BACKGROUND WORKER
pattern.  Instead of issuing the credential synchronously (which might
involve external API calls, DB writes, notifications), we enqueue a task
and return 202 Accepted immediately.  A separate worker process picks up
the task and handles it asynchronously.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.dependencies import require_user
from app.api.ratelimit import require_rate_limit
from app.models.principal import Principal
from app.services.task_queue import task_queue

router = APIRouter(prefix="/v1/credentials", tags=["credentials"])


class CredentialVerifyOut(BaseModel):
    id: str
    user_id: str
    credential_name: str
    issuer: str
    issued_at: int
    status: str
    valid: bool


class CredentialIssueIn(BaseModel):
    credential_id: str
    course_id: str


class CredentialIssueOut(BaseModel):
    task_id: str
    status: str


# In-memory store — will be replaced by Postgres repos.
_CREDENTIALS: dict[str, dict] = {}
_USER_CREDENTIALS: dict[str, dict] = {}


@router.get("/{credential_id}/verify", response_model=CredentialVerifyOut)
def verify_credential(
    credential_id: str,
) -> CredentialVerifyOut:
    uc = _USER_CREDENTIALS.get(credential_id)
    if uc is None:
        raise HTTPException(status_code=404, detail="credential not found")

    cred = _CREDENTIALS.get(uc["credential_id"])
    if cred is None:
        raise HTTPException(status_code=404, detail="credential definition not found")

    return CredentialVerifyOut(
        id=credential_id,
        user_id=uc["user_id"],
        credential_name=cred["name"],
        issuer=cred["issuer"],
        issued_at=uc["issued_at"],
        status=uc["status"],
        valid=uc["status"] == "issued",
    )


@router.post(
    "/issue",
    response_model=CredentialIssueOut,
    status_code=202,
    dependencies=[Depends(require_rate_limit())],
)
async def request_credential_issuance(
    body: CredentialIssueIn,
    principal: Annotated[Principal, Depends(require_user)],
) -> CredentialIssueOut:
    """Enqueue a credential issuance task for background processing.

    WHY 202 Accepted (not 201 Created):
    The credential hasn't been created yet — it's been ACCEPTED for
    processing.  The worker will create it asynchronously.

    HTTP status codes communicate intent:
      201 Created = "the resource exists now, here it is"
      202 Accepted = "I got your request, it'll be processed soon"

    The client can poll or receive a webhook when issuance completes.
    """
    task = await task_queue.enqueue(
        "credential_issuance",
        {
            "user_id": principal.user_id,
            "credential_id": body.credential_id,
            "course_id": body.course_id,
        },
    )
    return CredentialIssueOut(task_id=task.id, status="queued")
