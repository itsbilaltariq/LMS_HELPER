"""Basic sanity tests for configuration, logging, and health endpoint."""

import logging

from fastapi.testclient import TestClient

from app.config import Settings
from app.logging import JSONFormatter, RedactionFilter
from app.main import app


def test_settings_defaults():
    """Verify default settings reflect NUST LMS and Groq."""
    settings = Settings(APP_ENV="testing")
    assert "lms.nust.edu.pk" in settings.LMS_BASE_URL
    assert settings.GROQ_MODEL == "llama-3.3-70b-versatile"
    assert settings.GROQ_PARSER_MODEL == "llama-3.1-8b-instant"


def test_redaction_filter():
    """Verify Groq API keys are redacted from logs."""
    r_filter = RedactionFilter()
    formatter = JSONFormatter()

    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Using key gsk_1234567890abcdef1234567890abcdef for student session",
        args=(),
        exc_info=None,
    )
    r_filter.filter(record)
    formatted = formatter.format(record)

    assert "gsk_1234567890abcdef1234567890abcdef" not in formatted
    assert "[REDACTED]" in formatted


def test_health_endpoint():
    """Verify health endpoint returns status ok and correct LMS target."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["lms"] == "lms.nust.edu.pk"
    assert data["llm"] == "groq"
