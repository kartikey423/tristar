"""JWT authentication middleware for TriStar API.

Validates HS256 Bearer tokens, extracts role, and enforces RBAC.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from src.backend.core.config import settings

security = HTTPBearer()


def verify_webhook_signature(body: bytes, signature: Optional[str], secret: str) -> bool:
    """Verify HMAC-SHA256 signature from X-Webhook-Signature header.

    Uses constant-time comparison to prevent timing attacks.
    Returns False if signature is missing or malformed.
    """
    if not signature:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


class AuthUser(BaseModel):
    user_id: str
    role: str


def _decode_token(token: str) -> dict:
    """Decode and validate JWT. Raises HTTPException on failure."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {e}",
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> AuthUser:
    """Extract and validate the authenticated user from the Bearer token."""
    payload = _decode_token(credentials.credentials)

    user_id = payload.get("sub")
    role = payload.get("role", "")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject (sub) claim",
        )

    return AuthUser(user_id=user_id, role=role)


async def require_marketing_role(
    user: AuthUser = Depends(get_current_user),
) -> AuthUser:
    """Enforce that the caller has role='marketing'."""
    if user.role != "marketing":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role 'marketing' required; caller has role '{user.role}'",
        )
    return user


async def require_system_role(
    user: AuthUser = Depends(get_current_user),
) -> AuthUser:
    """Enforce that the caller has role='system' (service-to-service)."""
    if user.role != "system":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role 'system' required for this endpoint; caller has role '{user.role}'",
        )
    return user


async def require_marketing_or_system_role(
    user: AuthUser = Depends(get_current_user),
) -> AuthUser:
    """Enforce that the caller has role='marketing' or role='system'.

    Used for Hub write endpoints that are legitimately called by both marketers
    (via the frontend) and internal services (via service-to-service JWT).
    """
    if user.role not in ("marketing", "system"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Role 'marketing' or 'system' required; caller has role '{user.role}'"
            ),
        )
    return user
