"""Structured JSON logging with sensitive data redaction."""

import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any

# Sensitive patterns to redact
SENSITIVE_PATTERNS = [
    re.compile(r"gsk_[a-zA-Z0-9]{30,}", re.IGNORECASE),  # Groq API Keys
    re.compile(r"password['\"]\s*:\s*['\"][^'\"]+['\"]", re.IGNORECASE),
    re.compile(r"bearer\s+[a-zA-Z0-9_\-\.]+", re.IGNORECASE),
    re.compile(r"logintoken['\"]\s*:\s*['\"][^'\"]+['\"]", re.IGNORECASE),
]


class RedactionFilter(logging.Filter):
    """Filter that strips out sensitive keys and credentials before logging."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pattern in SENSITIVE_PATTERNS:
                record.msg = pattern.sub("[REDACTED]", record.msg)

        if record.args and isinstance(record.args, dict):
            clean_args = {}
            for k, v in record.args.items():
                if any(sec in k.lower() for sec in ("pass", "secret", "token", "key", "fernet")):
                    clean_args[k] = "[REDACTED]"
                else:
                    clean_args[k] = v
            record.args = clean_args

        return True


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure structured root logger."""
    logger = logging.getLogger("lms_helper")
    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    handler.addFilter(RedactionFilter())

    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False

    return logger
