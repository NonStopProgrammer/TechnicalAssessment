"""SEC-2.1 (AuthN) / SEC-2.2 (AuthZ/RBAC).

Standing in for Keycloak OIDC (see requirements/07-security-compliance-
requirements.md and ADR discussion) with a self-issued HS256 JWT carrying
the same claim shape (`sub`, `role`) a real OIDC token would carry after
claim mapping — swapping in Keycloak later only touches `get_current_user`
and `POST /auth/dev-token` (deleted entirely in production), never the
`require_roles` dependency or any endpoint.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from shared.config import get_settings
from shared.enums import UserRole

bearer_scheme = HTTPBearer(auto_error=True)


@dataclass
class AuthenticatedUser:
    user_id: str
    role: UserRole


def create_access_token(user_id: str, role: UserRole) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": user_id, "role": role.value, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> AuthenticatedUser:
    settings = get_settings()
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return AuthenticatedUser(user_id=payload["sub"], role=UserRole(payload["role"]))
    except (JWTError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired token") from exc


def require_roles(*allowed: UserRole):
    """SEC-2.2 role map: compliance_officer (query+screen), compliance_head
    (+report generation/trends), internal_auditor (read-only audit trail),
    platform_admin (ingestion/config, no query content access).
    """

    def _dependency(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"role '{user.role.value}' is not permitted to access this endpoint",
            )
        return user

    return _dependency
