"""Lab jobs management and cryptographic human approval gate."""

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import get_current_user, require_csrf
from app.logging import setup_logging
from app.models import ApprovalRequest, Job, JobStatus, User

logger = setup_logging()
jobs_router = APIRouter(prefix="/jobs", tags=["jobs"])

# In-memory jobs store (migrated to PostgreSQL in Phase 2 DB step)
JOBS_DB: dict[str, Job] = {}


class CreateJobPayload(BaseModel):
    course_id: str
    assignment_id: str
    title: str


@jobs_router.post("", dependencies=[Depends(require_csrf)])
async def create_job(
    payload: CreateJobPayload,
    current_user: Annotated[User, Depends(get_current_user)],
) -> Job:
    """Create a new lab assistance job."""
    job_id = str(uuid.uuid4())
    job = Job(
        id=job_id,
        user_id=current_user.id,
        course_id=payload.course_id,
        assignment_id=payload.assignment_id,
        title=payload.title,
        status=JobStatus.PENDING,
    )
    JOBS_DB[job_id] = job
    logger.info(f"Created job {job_id} for user {current_user.username}")
    return job


@jobs_router.get("")
async def list_jobs(current_user: Annotated[User, Depends(get_current_user)]) -> list[Job]:
    """List jobs belonging strictly to the authenticated user (prevents IDOR)."""
    return [job for job in JOBS_DB.values() if job.user_id == current_user.id]


@jobs_router.get("/{job_id}")
async def get_job(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> Job:
    """Get job details with IDOR protection."""
    job = JOBS_DB.get(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    if job.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return job


@jobs_router.post("/{job_id}/approve", dependencies=[Depends(require_csrf)])
async def approve_job(
    job_id: str,
    payload: ApprovalRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    """
    Cryptographic Human Approval Gate.
    Ensures that the artifact the student inspected and approved matches
    the exact SHA-256 digest of the artifact bundle.
    """
    job = JOBS_DB.get(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    if job.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    if not job.artifact_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job has no generated artifact to approve",
        )

    # Strictly verify cryptographic digest match
    if job.artifact_hash != payload.expected_artifact_hash:
        logger.warning(
            f"Digest mismatch on job {job_id}: "
            f"expected {job.artifact_hash}, got {payload.expected_artifact_hash}"
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Artifact digest mismatch! Artifact may have been tampered with or modified "
                "since review."
            ),
        )

    job.status = JobStatus.APPROVED
    job.updated_at = datetime.now(timezone.utc)
    logger.info(
        f"Job {job_id} approved by user {current_user.username} with digest {job.artifact_hash}"
    )

    return {
        "status": "approved",
        "job_id": job.id,
        "artifact_hash": job.artifact_hash,
    }
