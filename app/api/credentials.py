"""Credential verification endpoint.

Implements the credential issuance flow from data-model-notes-week4.md.
Credential issuance is service-layer (triggered on course completion).
This endpoint provides external verification: GET /v1/credentials/{id}/verify
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/v1/credentials", tags=["credentials"])


class CredentialVerifyOut(BaseModel):
    id: str
    user_id: str
    credential_name: str
    issuer: str
    issued_at: int
    status: str
    valid: bool


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
