import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import bcrypt
import jwt

from app.core.config import settings


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def _create_token(
    subject: str,
    token_type: TokenType,
    expires_delta: timedelta,
    jti: str | None = None,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type.value,
        "iat": now,
        "exp": now + expires_delta,
    }
    if jti is not None:
        payload["jti"] = jti
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(subject: uuid.UUID | str) -> str:
    """Create a short-lived, stateless access token for `subject` (user id)."""
    return _create_token(
        subject=str(subject),
        token_type=TokenType.ACCESS,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        jti=str(uuid.uuid4()),
    )


def create_refresh_token(subject: uuid.UUID | str, jti: uuid.UUID | str) -> str:
    """Create a refresh token whose `jti` maps to a `refresh_tokens` row for revocation."""
    return _create_token(
        subject=str(subject),
        token_type=TokenType.REFRESH,
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        jti=str(jti),
    )


def decode_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT. Raises `jwt.PyJWTError` on invalid/expired tokens."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


def hash_api_key(raw_key: str) -> str:
    """Hash an API key for storage/lookup. SHA-256 is sufficient since API keys
    are high-entropy random tokens, not low-entropy user-chosen passwords."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key. Returns `(raw_key, key_prefix, hashed_key)`.

    `raw_key` is shown to the user once; only `key_prefix` (for identification
    in listings) and `hashed_key` (for lookup) are persisted.
    """
    raw_key = f"sk_{secrets.token_urlsafe(24)}"
    key_prefix = raw_key[:11]
    return raw_key, key_prefix, hash_api_key(raw_key)
