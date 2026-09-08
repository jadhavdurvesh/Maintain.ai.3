"""
Auth building blocks: password hashing and JWT issuing/verification.

Deliberately lightweight — PBKDF2-HMAC-SHA256 (stdlib `hashlib`, no bcrypt/
passlib dependency) for passwords, and PyJWT (pure Python, no cryptography
backend needed for HS256) for tokens. Consistent with the rest of this
project's philosophy: real, correct implementations, minimal dependencies.
"""
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt

JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-insecure-secret-change-this-in-any-real-deployment")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))

PBKDF2_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ITERATIONS)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, digest_hex = stored_hash.split("$")
    except (ValueError, AttributeError):
        return False
    check = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ITERATIONS)
    return secrets.compare_digest(check.hex(), digest_hex)


def create_access_token(user_id: int, organization_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "org": organization_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
