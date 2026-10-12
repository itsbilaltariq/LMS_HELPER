"""Cryptographic security utilities: Argon2id, Fernet, HMAC-CSRF, and SHA-256 gates."""

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Argon2id hasher configured for memory and time resistance
ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MiB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

# Dummy hash for timing attack mitigation when user is not found
DUMMY_HASH = ph.hash("timing-safety-dummy-password")


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return ph.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    """Verify password against Argon2id hash with timing safety."""
    try:
        return ph.verify(stored_hash, password)
    except (VerifyMismatchError, Exception):
        return False


def dummy_verify(password: str) -> bool:
    """Execute a real hash verification to equalize response timing when user not found."""
    try:
        ph.verify(DUMMY_HASH, password)
    except Exception:
        pass
    return False


def generate_fernet_key() -> str:
    """Generate a fresh URL-safe 32-byte Fernet key."""
    return Fernet.generate_key().decode()


def encrypt_credential(plaintext: str, fernet_key: str) -> str:
    """Encrypt NUST LMS credential with Fernet."""
    f = Fernet(fernet_key.encode())
    return f.encrypt(plaintext.encode()).decode()


def decrypt_credential(ciphertext: str, fernet_key: str) -> str:
    """Decrypt NUST LMS credential with Fernet in memory."""
    f = Fernet(fernet_key.encode())
    return f.decrypt(ciphertext.encode()).decode()


def generate_session_id() -> str:
    """Generate a secure random session ID."""
    return secrets.token_urlsafe(32)


def generate_csrf_token(session_id: str, app_secret: str) -> str:
    """Generate HMAC-SHA256 CSRF token cryptographically bound to session ID."""
    return hmac.new(
        key=app_secret.encode(),
        msg=session_id.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()


def verify_csrf_token(session_id: str, token: str, app_secret: str) -> bool:
    """Constant-time verification of HMAC-CSRF token."""
    expected = generate_csrf_token(session_id, app_secret)
    return hmac.compare_digest(expected, token)


def compute_sha256(data: bytes) -> str:
    """Compute SHA-256 hex digest for code or zip artifact."""
    return hashlib.sha256(data).hexdigest()


def compute_file_sha256(file_path: str) -> str:
    """Compute SHA-256 digest of a local artifact file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inject strict security headers for ASVS compliance."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), camera=(), microphone=(), payment=()"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; frame-ancestors 'none'; object-src 'none';"
        )
        return response
