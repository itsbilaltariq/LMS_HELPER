"""Unit tests for Phase 8 submission bundle builder and digest verification."""

from pathlib import Path

import pytest

from workers.bundle import (
    BundleTamperingError,
    build_submission_bundle,
    generate_review_summary,
    verify_bundle_digest,
)


def test_build_submission_bundle(tmp_path: Path):
    """Verify bundle packager creates zip, manifest, and computes SHA-256."""
    src_dir = tmp_path / "workspace"
    src_dir.mkdir()

    # Create dummy deliverable files
    (src_dir / "solution.py").write_text("print('nust')", encoding="utf-8")
    (src_dir / "report.txt").write_text("Lab report content", encoding="utf-8")

    out_zip = tmp_path / "submission.zip"
    meta = build_submission_bundle(
        source_dir=src_dir,
        deliverable_files=["solution.py", "report.txt"],
        output_zip_path=out_zip,
        job_id="job_test_001",
        viva_questions=["What is the time complexity?"],
    )

    assert out_zip.exists()
    assert "bundle_sha256" in meta
    assert len(meta["bundle_sha256"]) == 64
    assert len(meta["manifest"]["files"]) == 2

    # Verify untampered bundle digest matches
    assert verify_bundle_digest(out_zip, meta["bundle_sha256"]) is True


def test_tampered_bundle_rejection(tmp_path: Path):
    """Verify tampering detection raises BundleTamperingError."""
    src_dir = tmp_path / "workspace"
    src_dir.mkdir()
    (src_dir / "code.py").write_text("print(1)", encoding="utf-8")

    out_zip = tmp_path / "tamper_test.zip"
    meta = build_submission_bundle(
        source_dir=src_dir,
        deliverable_files=["code.py"],
        output_zip_path=out_zip,
        job_id="job_tamper_001",
    )

    # Tamper with the zip file by modifying bytes
    with open(out_zip, "ab") as f:
        f.write(b"tampered_extra_bytes")

    with pytest.raises(BundleTamperingError):
        verify_bundle_digest(out_zip, meta["bundle_sha256"])


def test_review_summary_generation(tmp_path: Path):
    """Verify review markdown generation contains required review metadata."""
    meta = {
        "bundle_sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        "manifest": {
            "files": [
                {
                    "file": "main.py",
                    "sha256": "1234567890abcdef",
                    "bytes": 42,
                }
            ],
            "viva_questions": ["Explain recursion"],
        },
    }

    summary = generate_review_summary(
        bundle_metadata=meta,
        lab_title="Lab 2 Trees",
        test_results_summary="All 5 unit tests passed.",
        deadline_str="2026-10-20 23:59",
    )

    assert "Lab Submission Review: Lab 2 Trees" in summary
    assert "abcdef1234567890" in summary
    assert "main.py" in summary
    assert "Explain recursion" in summary
    assert "2026-10-20 23:59" in summary


def test_build_multi_format_submission_bundle(tmp_path: Path):
    """Verify auto-generation of .ipynb, .docx, and .xlsx deliverables during bundle creation."""
    src_dir = tmp_path / "workspace_multi"
    src_dir.mkdir()

    out_zip = tmp_path / "multi_submission.zip"
    meta = build_submission_bundle(
        source_dir=src_dir,
        deliverable_files=["task.ipynb", "report.docx", "data.xlsx"],
        output_zip_path=out_zip,
        job_id="job_multi_999",
        lab_title="Digital Logic Lab 5",
        solution_code="module alu(); endmodule",
        explanation="ALU module with arithmetic and logic operations.",
        viva_questions=["What is an ALU flags register?"],
    )

    assert out_zip.exists()
    assert (src_dir / "task.ipynb").exists()
    assert (src_dir / "report.docx").exists()
    assert (src_dir / "data.xlsx").exists()

    manifest = meta["manifest"]
    files = {f["file"]: f for f in manifest["files"]}
    assert files["task.ipynb"]["mime_type"] == "application/x-ipynb+json"
    assert "wordprocessingml" in files["report.docx"]["mime_type"]
    assert "spreadsheetml" in files["data.xlsx"]["mime_type"]

    assert verify_bundle_digest(out_zip, meta["bundle_sha256"]) is True
