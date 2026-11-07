import time
from collections import defaultdict, deque
from datetime import timedelta
from typing import Annotated

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db, utcnow

settings = get_settings()
ALGORITHM = "HS256"
bearer = HTTPBearer(auto_error=False)

ROLES = {
    "super_admin": "Manage facilities, users, settings; view all analytics",
    "safety_manager": "Monitor risk, review predictions, manage incidents, assign preventive actions",
    "plant_manager": "Operational dashboards, machine monitoring, reports, maintenance tracking",
    "maintenance_engineer": "View assigned machines, update and resolve maintenance tasks",
    "safety_officer": "Review hazards, create incident reports, update emergency response records",
}


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:72], hashed.encode())
    except ValueError:
        return False


def create_access_token(subject: str, role: str) -> str:
    exp = utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({"sub": subject, "role": role, "exp": exp}, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        return None


def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Session = Depends(get_db),
):
    from app.models import User

    if not creds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    payload = decode_token(creds.credentials)
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
    return user


def require_roles(*roles: str):
    """Super admin always passes; others must be in `roles`."""

    def checker(user=Depends(get_current_user)):
        if user.role != "super_admin" and user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Role '{user.role}' is not permitted to perform this action")
        return user

    return checker


_hits: dict[str, deque] = defaultdict(deque)


def rate_limit(request: Request):
    """Tiny in-memory sliding-window limiter (per client IP) for auth endpoints.
    For multi-instance deployments use Redis (see docs)."""
    limit = settings.login_rate_limit_per_minute
    key = f"{request.client.host if request.client else 'x'}:{request.url.path}"
    now = time.time()
    q = _hits[key]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts, slow down")
    q.append(now)
