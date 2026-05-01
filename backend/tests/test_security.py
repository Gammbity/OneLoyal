from datetime import timedelta

from cryptography.fernet import Fernet

from app.core.errors import UnauthorizedError, ValidationAppError
from app.core.security import (
    create_access_token,
    decode_token,
    decrypt_secret,
    encrypt_secret,
    hash_password,
    verify_password,
)
from app.core.settings import Settings


def test_password_hash_and_verify() -> None:
    settings = Settings(
        password_hash_time_cost=1,
        password_hash_memory_cost=8192,
        password_hash_parallelism=1,
    )

    hashed = hash_password("correct horse battery staple", settings=settings)

    assert hashed != "correct horse battery staple"
    assert verify_password("correct horse battery staple", hashed, settings=settings)
    assert not verify_password("wrong password", hashed, settings=settings)


def test_jwt_create_and_decode() -> None:
    settings = Settings(secret_key="test-secret-key-with-enough-length")

    token = create_access_token(
        subject="user-123",
        expires_delta=timedelta(minutes=5),
        extra_claims={"role": "admin"},
        settings=settings,
    )
    payload = decode_token(token, settings=settings)

    assert payload["sub"] == "user-123"
    assert payload["role"] == "admin"
    assert payload["token_type"] == "access"


def test_jwt_decode_rejects_invalid_token() -> None:
    settings = Settings(secret_key="test-secret-key-with-enough-length")

    try:
        decode_token("invalid.token.value", settings=settings)
    except UnauthorizedError as exc:
        assert exc.code == "unauthorized"
    else:
        raise AssertionError("Invalid token should raise UnauthorizedError")


def test_encryption_roundtrip() -> None:
    settings = Settings(encryption_key=Fernet.generate_key().decode("utf-8"))

    encrypted = encrypt_secret("erp-secret-value", settings=settings)

    assert encrypted != "erp-secret-value"
    assert decrypt_secret(encrypted, settings=settings) == "erp-secret-value"


def test_decrypt_rejects_invalid_ciphertext() -> None:
    settings = Settings(encryption_key=Fernet.generate_key().decode("utf-8"))

    try:
        decrypt_secret("not-a-valid-token", settings=settings)
    except ValidationAppError as exc:
        assert exc.code == "invalid_encrypted_secret"
    else:
        raise AssertionError("Invalid ciphertext should raise ValidationAppError")
