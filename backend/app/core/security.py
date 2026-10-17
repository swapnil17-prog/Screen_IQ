"""Password hashing, JWT access tokens and opaque candidate-link tokens."""

import base64
import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import settings

JWT_ALGORITHM = "HS256"
# bcrypt only uses the first 72 bytes; reject longer passwords at the schema layer.
MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


# Constant-time dummy check used when a login email doesn't exist, so response
# timing doesn't reveal which emails are registered.
_DUMMY_HASH = bcrypt.hashpw(b"timing-equaliser", bcrypt.gensalt(rounds=12)).decode()


def burn_password_check(password: str) -> None:
    verify_password(password, _DUMMY_HASH)


def create_access_token(user_id: uuid.UUID, organization_id: uuid.UUID, role: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "org": str(organization_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
        "type": "access",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Raises jwt.PyJWTError on any invalid / expired token."""
    payload = jwt.decode(token, settings.secret_key, algorithms=[JWT_ALGORITHM])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("wrong token type")
    return payload


def generate_link_token() -> str:
    """Opaque, URL-safe token for emailed account links — password reset, invitations (256 bits)."""
    return secrets.token_urlsafe(32)


def derive_link_token(session_id: uuid.UUID, version: int) -> str:
    """
    Candidate interview-link token, HMAC-derived from the session id and link version.

    Only its hash is stored, yet the server can re-create the same link for reminder
    emails. Forging one needs SECRET_KEY, which already guards every session token.
    """
    mac = hmac.new(settings.secret_key.encode("utf-8"), f"interview-link:{session_id}:{version}".encode(),
                   hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).rstrip(b"=").decode("ascii")


def hash_token(token: str) -> str:
    """Only the SHA-256 of link tokens is stored, so a DB leak doesn't leak live links."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
