"""Artifact bundle builder, manifest generator, and cryptographic review verification."""

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.logging import setup_logging
from app.security import compute_file_sha256
from workers.formatters import (
    convert_solution_to_notebook,
    convert_solution_to_word,
    create_excel_spreadsheet,
)

logger = setup_logging()

MIME_MAP: dict[str, str] = {
    ".ipynb": "application/x-ipynb+json",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pdf": "application/pdf",
    ".py": "text/x-python",
    ".cpp": "text/x-c++src",
    ".java": "text/x-java-source",
    ".zip": "application/zip",
    ".txt": "text/plain",
    ".md": "text/markdown",
}


class BundleTamperingError(Exception):
    """Raised when an artifact bundle digest does not match the approved hash."""

    pass


def build_submission_bundle(
    source_dir: str | Path,
    deliverable_files: list[str],
    output_zip_path: str | Path,
    job_id: str,
    lab_title: str = "Lab Assignment",
    solution_code: str | None = None,
    explanation: str | None = None,
    viva_questions: list[str] | None = None,
) -> dict[str, Any]:
    """
    Pack validated deliverables into a submission zip and produce a cryptographic manifest.
    Auto-materializes requested format (.ipynb, .docx, .xlsx) if code/explanation is provided.
    Returns bundle metadata including the aggregate SHA-256 digest.
    """
    src = Path(source_dir).resolve()
    out_zip = Path(output_zip_path).resolve()
    out_zip.parent.mkdir(parents=True, exist_ok=True)

    manifest_files: list[dict[str, Any]] = []

    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
        for rel_file in deliverable_files:
            file_path = src / rel_file

            # If deliverable does not exist, check if we can generate it
            if not file_path.exists() and solution_code:
                suffix = file_path.suffix.lower()
                if suffix == ".ipynb":
                    convert_solution_to_notebook(
                        title=lab_title,
                        solution_code=solution_code,
                        walkthrough=explanation or "Solution implementation",
                        output_path=file_path,
                        viva_questions=viva_questions,
                    )
                elif suffix == ".docx":
                    convert_solution_to_word(
                        title=lab_title,
                        solution_code=solution_code,
                        walkthrough=explanation or "Solution implementation",
                        output_path=file_path,
                        viva_questions=viva_questions,
                    )
                elif suffix == ".xlsx":
                    create_excel_spreadsheet(
                        sheets_data={"Summary": [["Item", "Detail"], [lab_title, "Completed"]]},
                        output_path=file_path,
                    )

            if not file_path.exists():
                raise FileNotFoundError(f"Deliverable file '{rel_file}' not found in workspace")

            # Calculate individual file SHA-256 and MIME
            file_hash = compute_file_sha256(str(file_path))
            file_size = file_path.stat().st_size
            mime_type = MIME_MAP.get(file_path.suffix.lower(), "application/octet-stream")

            manifest_files.append(
                {
                    "file": rel_file,
                    "sha256": file_hash,
                    "bytes": file_size,
                    "mime_type": mime_type,
                }
            )

            # Add to zip archive with relative path
            zipf.write(file_path, arcname=rel_file)

        # Include manifest inside the zip archive as well
        manifest_data = {
            "job_id": job_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "files": manifest_files,
            "viva_questions": viva_questions or [],
        }
        zipf.writestr("manifest.json", json.dumps(manifest_data, indent=2))

    # Calculate overall bundle archive digest
    bundle_digest = compute_file_sha256(str(out_zip))
    logger.info(f"Built bundle {out_zip.name} with SHA-256: {bundle_digest}")

    return {
        "zip_path": str(out_zip),
        "bundle_sha256": bundle_digest,
        "manifest": manifest_data,
    }


def verify_bundle_digest(bundle_zip_path: str | Path, expected_digest: str) -> bool:
    """
    Verify that the artifact zip to be uploaded exactly matches the approved digest.
    Refuses upload on mismatch.
    """
    computed = compute_file_sha256(str(bundle_zip_path))
    if computed != expected_digest:
        logger.error(f"Digest mismatch! Expected: {expected_digest}, Computed: {computed}")
        raise BundleTamperingError(
            f"Bundle tampering detected! Expected {expected_digest}, but got {computed}"
        )
    return True


def generate_review_summary(
    bundle_metadata: dict[str, Any],
    lab_title: str,
    test_results_summary: str,
    deadline_str: str | None = None,
) -> str:
    """Produce human-readable review markdown for student approval."""
    lines: list[str] = [
        f"# Lab Submission Review: {lab_title}",
        f"\n**Cryptographic Bundle Digest (SHA-256):** `{bundle_metadata['bundle_sha256']}`",
        f"**Generated At:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
    ]

    if deadline_str:
        lines.append(f"**LMS Deadline:** {deadline_str}")

    lines.append("\n## Included Deliverable Files")
    for f in bundle_metadata["manifest"]["files"]:
        lines.append(f"- **{f['file']}** ({f['bytes']} bytes) - SHA-256: `{f['sha256'][:16]}...`")

    lines.append(f"\n## Automated Verification & Test Results\n{test_results_summary}")

    viva = bundle_metadata["manifest"].get("viva_questions", [])
    if viva:
        lines.append("\n## Viva / Oral Exam Prep")
        for q in viva:
            lines.append(f"- {q}")

    lines.append(
        "\n> [!IMPORTANT]\n"
        "> Inspect all changes before approving. Once approved, the exact SHA-256 digest is locked "
        "and sent to the NUST LMS upload worker."
    )

    return "\n".join(lines)
