"""Phone OTP + JWT auth. In dev (OTP_DEV_MODE=true) the OTP is always 123456 and is echoed back."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app import cache
from app.config import get_settings
from app.db import get_db
from app.models import User

DEV_OTP = "123456"
MAX_ATTEMPTS = 5
bearer = HTTPBearer(auto_error=False)


def _hash(phone: str, otp: str) -> str:
    return hmac.new(get_settings().jwt_secret.encode(), f"{phone}:{otp}".encode(), hashlib.sha256).hexdigest()


def issue_otp(phone: str) -> str:
    s = get_settings()
    otp = DEV_OTP if s.otp_dev_mode else f"{secrets.randbelow(10**6):06d}"
    c = cache.client()
    c.set(f"otp:{phone}", _hash(phone, otp), ex=s.otp_ttl_seconds)
    c.delete(f"otp_attempts:{phone}")
    return otp


def verify_otp(phone: str, otp: str) -> bool:
    c = cache.client()
    attempts = c.incr(f"otp_attempts:{phone}")
    c.expire(f"otp_attempts:{phone}", get_settings().otp_ttl_seconds)
    if attempts > MAX_ATTEMPTS:
        c.delete(f"otp:{phone}")
        return False
    stored = c.get(f"otp:{phone}")
    if not stored or not hmac.compare_digest(stored, _hash(phone, otp)):
        return False
    c.delete(f"otp:{phone}")
    c.delete(f"otp_attempts:{phone}")
    return True


def create_token(user: User) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    payload = {"sub": str(user.id), "role": user.role, "iat": now, "exp": now + timedelta(hours=s.jwt_ttl_hours)}
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    try:
        payload = jwt.decode(creds.credentials, get_settings().jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired token") from None
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found or disabled")
    return user


def require(*roles: str):
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"requires role: {', '.join(roles)}")
        return user

    return dep
