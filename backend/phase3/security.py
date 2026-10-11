from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError


PASSWORD_MIN_LENGTH = max(12, int(os.getenv("CRASHGUARD_PASSWORD_MIN_LENGTH", "12")))
SESSION_TTL_SECONDS = max(
    300, int(os.getenv("CRASHGUARD_SESSION_TTL_SECONDS", str(7 * 24 * 60 * 60)))
)
PASSWORD_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def validate_password(password: str) -> str:
    if len(password or "") < PASSWORD_MIN_LENGTH:
        raise ValueError(
            f"Password must contain at least {PASSWORD_MIN_LENGTH} characters."
        )
    if not any(char.isalpha() for char in password) or not any(
        char.isdigit() for char in password
    ):
        raise ValueError("Password must contain at least one letter and one number.")
    return password


def hash_password(password: str) -> str:
    return PASSWORD_HASHER.hash(validate_password(password))


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return PASSWORD_HASHER.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError, TypeError):
        return False


def generate_temporary_password() -> str:
    return f"Cg9!{secrets.token_urlsafe(18)}"


def generate_session_token() -> str:
    return secrets.token_urlsafe(48)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_expiry() -> datetime:
    return utcnow() + timedelta(seconds=SESSION_TTL_SECONDS)
