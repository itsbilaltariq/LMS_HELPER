"""Data models for users, sessions, jobs, and approval gates."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    PENDING = "pending"
    FETCHING = "fetching"
    PARSING = "parsing"
    SOLVING = "solving"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    FAILED = "failed"


class User(BaseModel):
    id: str
    username: str
    password_hash: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SessionData(BaseModel):
    session_id: str
    user_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime


class LMSCredential(BaseModel):
    user_id: str
    lms_username: str
    encrypted_password: str
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Job(BaseModel):
    id: str
    user_id: str
    course_id: str
    assignment_id: str
    title: str
    status: JobStatus = JobStatus.PENDING
    artifact_hash: str | None = None
    artifact_path: str | None = None
    explanation: str | None = None
    viva_questions: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ApprovalRequest(BaseModel):
    job_id: str
    expected_artifact_hash: str


class AuditLogEntry(BaseModel):
    id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    user_id: str | None = None
    action: str
    ip_address: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
