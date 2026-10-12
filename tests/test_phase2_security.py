"""Unit tests for Phase 2 Secure API core."""

import pytest
from fastapi.testclient import TestClient

from app.auth import SESSIONS_DB, USERS_DB
from app.config import Settings, get_settings
from app.jobs import JOBS_DB
from app.main import app
from app.models import Job, JobStatus, SessionData, User
from app.security import (
    compute_sha256,
    decrypt_credential,
    encrypt_credential,
    generate_csrf_token,
    generate_fernet_key,
    hash_password,
    verify_csrf_token,
    verify_password,
)

client = TestClient(app)
test_settings = Settings(
    APP_ENV="testing",
    APP_SECRET="test-super-secret-key-for-csrf-hmac-32chars",
    FERNET_KEY=generate_fernet_key(),
)
app.dependency_overrides[get_settings] = lambda: test_settings


@pytest.fixture(autouse=True)
def clean_dbs():
    """Clear in-memory state between tests."""
    USERS_DB.clear()
    SESSIONS_DB.clear()
    JOBS_DB.clear()


def test_argon2id_hashing():
    """Verify Argon2id password hashing and verification."""
    password = "NustPassword@2026"
    pw_hash = hash_password(password)
    assert verify_password(pw_hash, password) is True
    assert verify_password(pw_hash, "wrong-password") is False


def test_fernet_credential_encryption():
    """Verify Fernet encryption and decryption of LMS credentials."""
    key = test_settings.FERNET_KEY
    plaintext_creds = "SuperSecretQalamPass123"
    cipher = encrypt_credential(plaintext_creds, key)
    assert cipher != plaintext_creds
    decrypted = decrypt_credential(cipher, key)
    assert decrypted == plaintext_creds


def test_csrf_token_binding():
    """Verify CSRF token is cryptographically bound to session ID."""
    session_id = "sess_user123_abc"
    token = generate_csrf_token(session_id, test_settings.APP_SECRET)

    # Valid token
    assert verify_csrf_token(session_id, token, test_settings.APP_SECRET) is True

    # Bad session
    assert verify_csrf_token("other_session", token, test_settings.APP_SECRET) is False

    # Tampered token
    assert verify_csrf_token(session_id, token + "x", test_settings.APP_SECRET) is False


def test_security_headers_present():
    """Verify ASVS required security headers are attached."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert "Content-Security-Policy" in resp.headers


def test_approval_gate_accepts_valid_digest_and_rejects_tampered():
    """Test cryptographic approval gate ensures exact SHA-256 digest match."""
    user = User(
        id="u1",
        username="student1",
        password_hash=hash_password("pw"),
    )
    USERS_DB[user.id] = user

    # Create session
    session_id = "sess_student1"
    from datetime import datetime, timedelta, timezone

    SESSIONS_DB[session_id] = SessionData(
        session_id=session_id,
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    # Generate CSRF token
    csrf_token = generate_csrf_token(session_id, test_settings.APP_SECRET)

    # Create job with artifact hash
    artifact_code = b"def solve_lab():\n    return 'nust_done'\n"
    artifact_hash = compute_sha256(artifact_code)

    job = Job(
        id="job123",
        user_id=user.id,
        course_id="CS110",
        assignment_id="Lab04",
        title="NUST Lab 4",
        status=JobStatus.AWAITING_APPROVAL,
        artifact_hash=artifact_hash,
    )
    JOBS_DB[job.id] = job

    # Test tampering rejection (modified digest)
    tampered_digest = compute_sha256(b"def solve_lab():\n    return 'tampered'\n")
    resp_tampered = client.post(
        f"/jobs/{job.id}/approve",
        json={"job_id": job.id, "expected_artifact_hash": tampered_digest},
        cookies={"__Host-session": session_id},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp_tampered.status_code == 409
    assert "Artifact digest mismatch" in resp_tampered.json()["detail"]
    assert JOBS_DB[job.id].status == JobStatus.AWAITING_APPROVAL

    # Test valid approval
    resp_valid = client.post(
        f"/jobs/{job.id}/approve",
        json={"job_id": job.id, "expected_artifact_hash": artifact_hash},
        cookies={"__Host-session": session_id},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp_valid.status_code == 200
    assert resp_valid.json()["status"] == "approved"
    assert JOBS_DB[job.id].status == JobStatus.APPROVED


def test_idor_protection():
    """Verify User B cannot access or approve User A's jobs."""
    user_a = User(id="ua", username="alice", password_hash=hash_password("pw"))
    user_b = User(id="ub", username="bob", password_hash=hash_password("pw"))
    USERS_DB[user_a.id] = user_a
    USERS_DB[user_b.id] = user_b

    from datetime import datetime, timedelta, timezone

    session_b = "sess_bob"
    SESSIONS_DB[session_b] = SessionData(
        session_id=session_b,
        user_id=user_b.id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    csrf_b = generate_csrf_token(session_b, test_settings.APP_SECRET)

    job_a = Job(
        id="job_a_private",
        user_id=user_a.id,
        course_id="CS212",
        assignment_id="Lab02",
        title="Alice's Lab",
        status=JobStatus.PENDING,
    )
    JOBS_DB[job_a.id] = job_a

    # User B tries to read User A's job
    resp = client.get(
        f"/jobs/{job_a.id}",
        cookies={"__Host-session": session_b},
        headers={"X-CSRF-Token": csrf_b},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Access denied"
