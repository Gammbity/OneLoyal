from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from argon2.low_level import Type
from cryptography.fernet import Fernet, InvalidToken

from app.core.errors import UnauthorizedError, ValidationAppError
from app.core.settings import Settings, get_settings


def generate_secure_token(byte_length: int = 32) -> str:
    return token_urlsafe(byte_length)


def _get_password_hasher(settings: Settings | None = None) -> PasswordHasher:
    settings = settings or get_settings()
    return PasswordHasher(
        time_cost=settings.password_hash_time_cost,
        memory_cost=settings.password_hash_memory_cost,
        parallelism=settings.password_hash_parallelism,
        type=Type.ID,
    )


def hash_password(password: str, settings: Settings | None = None) -> str:
    return _get_password_hasher(settings).hash(password)


def verify_password(
    password: str,
    hashed_password: str,
    settings: Settings | None = None,
) -> bool:
    try:
        return _get_password_hasher(settings).verify(hashed_password, password)
    except (VerifyMismatchError, VerificationError):
        return False


def create_access_token(
    *,
    subject: str,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> str:
    settings = settings or get_settings()
    now = datetime.now(UTC)
    expires_at = now + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    claims: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": expires_at,
        "token_type": "access",
    }
    if extra_claims:
        claims.update(extra_claims)

    return jwt.encode(claims, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    try:
        return jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError(
            message="Token has expired.",
            details={"reason": "expired"},
        ) from exc
    except jwt.PyJWTError as exc:
        raise UnauthorizedError(
            message="Invalid token.",
            details={"reason": "invalid"},
        ) from exc


def _get_fernet(settings: Settings | None = None) -> Fernet:
    settings = settings or get_settings()
    try:
        return Fernet(settings.encryption_key.encode("utf-8"))
    except ValueError as exc:
        raise RuntimeError(
            "ENCRYPTION_KEY must be a valid Fernet key. Generate one with "
            "`python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\"`."
        ) from exc


def encrypt_secret(plain_text: str, settings: Settings | None = None) -> str:
    return _get_fernet(settings).encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_secret(cipher_text: str, settings: Settings | None = None) -> str:
    try:
        decrypted = _get_fernet(settings).decrypt(cipher_text.encode("utf-8"))
        return decrypted.decode("utf-8")
    except InvalidToken as exc:
        raise ValidationAppError(
            message="Encrypted secret is invalid.",
            code="invalid_encrypted_secret",
        ) from exc
