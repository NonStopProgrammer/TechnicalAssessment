"""DEV-ONLY token issuance standing in for a Keycloak OIDC login redirect
(SEC-2.1). An endpoint that mints a token for any caller-supplied user_id
and role is explicitly not something a real deployment ships — delete this
file when wiring up Keycloak; nothing else in `backend/` depends on it
existing beyond `require_roles`'s JWT-decode contract.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from backend.core.security import create_access_token
from shared.enums import UserRole

router = APIRouter(tags=["auth"])


class DevTokenRequest(BaseModel):
    user_id: str
    role: UserRole


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/auth/dev-token", response_model=TokenResponse)
def issue_dev_token(payload: DevTokenRequest) -> TokenResponse:
    return TokenResponse(access_token=create_access_token(payload.user_id, payload.role))
