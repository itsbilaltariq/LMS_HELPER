"""Authentication, session lifecycle, and rate-limiting endpoints."""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.logging import setup_logging
from app.models import LMSCredential, SessionData, User
from app.security import (
    dummy_verify,
    encrypt_credential,
    generate_csrf_token,
    generate_session_id,
    verify_csrf_token,
    verify_password,
)

logger = setup_logging()
auth_router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory storage stores (replaced by Postgres in Phase 2 DB migration)
USERS_DB: dict[str, User] = {}
SESSIONS_DB: dict[str, SessionData] = {}
LMS_CREDS_DB: dict[str, LMSCredential] = {}

# Simple in-memory rate limiter for login attempts (per IP)
LOGIN_ATTEMPTS: dict[str, list[datetime]] = defaultdict(list)
RATE_LIMIT_WINDOW_SECONDS = 300
MAX_LOGIN_ATTEMPTS = 5


class LoginPayload(BaseModel):
    username: str
    password: str


class LMSCredentialPayload(BaseModel):
    lms_username: str
    lms_password: str


def check_login_rate_limit(client_ip: str) -> None:
    """Enforce rate limits on login attempts."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)
    attempts = [t for t in LOGIN_ATTEMPTS[client_ip] if t > cutoff]
    LOGIN_ATTEMPTS[client_ip] = attempts

    if len(attempts) >= MAX_LOGIN_ATTEMPTS:
        logger.warning(f"Login rate limit exceeded for IP: {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again in 5 minutes.",
        )


async def get_current_user(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    """FastAPI Dependency: Extract authenticated user from secure session cookie."""
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not session_id or session_id not in SESSIONS_DB:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    session = SESSIONS_DB[session_id]
    if datetime.now(timezone.utc) > session.expires_at:
        del SESSIONS_DB[session_id]
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired",
        )

    user = USERS_DB.get(session.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


async def require_csrf(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    x_csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> None:
    """Validate HMAC CSRF token against session cookie."""
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not session_id or not x_csrf_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing or invalid",
        )

    if not verify_csrf_token(session_id, x_csrf_token, settings.APP_SECRET):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token verification failed",
        )


@auth_router.post("/login")
async def login(
    payload: LoginPayload,
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    """Secure login endpoint with timing defense and cookie tokens."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    check_login_rate_limit(client_ip)

    user = next((u for u in USERS_DB.values() if u.username == payload.username), None)
    if not user:
        dummy_verify(payload.password)
        LOGIN_ATTEMPTS[client_ip].append(datetime.now(timezone.utc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not verify_password(user.password_hash, payload.password):
        LOGIN_ATTEMPTS[client_ip].append(datetime.now(timezone.utc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Reset attempts on success
    LOGIN_ATTEMPTS[client_ip] = []

    # Generate session ID and bound CSRF token
    session_id = generate_session_id()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
    SESSIONS_DB[session_id] = SessionData(
        session_id=session_id,
        user_id=user.id,
        expires_at=expires_at,
    )

    csrf_token = generate_csrf_token(session_id, settings.APP_SECRET)

    # Set secure cookies
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=settings.SECURE_COOKIES,
        samesite="strict",
        max_age=7200,
        path="/",
    )
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,  # JavaScript must read to send in X-CSRF-Token header
        secure=settings.SECURE_COOKIES,
        samesite="strict",
        max_age=7200,
        path="/",
    )

    logger.info(f"User {user.username} logged in successfully")
    return {"status": "authenticated", "username": user.username}


@auth_router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    """Logout endpoint terminating session."""
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if session_id and session_id in SESSIONS_DB:
        del SESSIONS_DB[session_id]

    response.delete_cookie(settings.SESSION_COOKIE_NAME, path="/")
    response.delete_cookie(settings.CSRF_COOKIE_NAME, path="/")
    return {"status": "logged_out"}


@auth_router.post("/lms-credentials", dependencies=[Depends(require_csrf)])
async def save_lms_credentials(
    payload: LMSCredentialPayload,
    current_user: Annotated[User, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    """Store student's NUST LMS credentials encrypted with Fernet."""
    if not settings.FERNET_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="FERNET_KEY not configured on server",
        )

    encrypted_pw = encrypt_credential(payload.lms_password, settings.FERNET_KEY)
    LMS_CREDS_DB[current_user.id] = LMSCredential(
        user_id=current_user.id,
        lms_username=payload.lms_username,
        encrypted_password=encrypted_pw,
    )
    logger.info(f"Updated NUST LMS credentials for user {current_user.username}")
    return {"status": "credentials_saved", "lms_username": payload.lms_username}


@auth_router.get("/me")
async def get_me(current_user: Annotated[User, Depends(get_current_user)]) -> dict[str, str]:
    """Get current authenticated user information."""
    return {"id": current_user.id, "username": current_user.username}
