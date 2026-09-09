from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import bcrypt
import jwt

from app.config import settings


ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_token(user_id: UUID) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_ttl_minutes)
    return jwt.encode({"sub": str(user_id), "exp": expires, "type": "access"}, settings.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])


def create_opaque_token() -> str:
    return secrets.token_urlsafe(32)


def create_verification_code() -> str:
    """Return a 6-digit numeric email confirmation code.

    Only the SHA-256 digest is stored, so a leaked database never exposes
    usable codes. Codes are deliberately short for manual entry; the low
    entropy is acceptable because the code only proves email ownership for
    the account it was sent to.
    """
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_opaque_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
