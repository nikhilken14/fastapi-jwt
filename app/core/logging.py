"""
Structured logging setup.

Production services log as JSON (one object per line) instead of free-form
text, because those logs get shipped to something like ELK / Loki / CloudWatch
that indexes and searches on fields - "give me every ERROR log for user_id=42"
is only possible if the logs are structured, not just readable by a human.

This module configures the root logger once, at startup, so every
`logging.getLogger(__name__)` call anywhere in the app automatically
gets JSON output with a consistent shape.
"""

import logging
import sys
from datetime import datetime, timezone
import json


class JsonFormatter(logging.Formatter):
    """Formats each log record as a single JSON line.

    Fields included: timestamp, level, logger name, the message itself,
    and (if present) exception info - enough to be genuinely useful in
    a log aggregator without being noisy.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(log_level: str = "INFO") -> None:
    """Set up the root logger for the whole process.

    Call this exactly once, at application startup (see app/main.py).

    Args:
        log_level: Minimum severity to emit, e.g. "INFO", "DEBUG", "WARNING".
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]  # replace any default handlers, avoid duplicate logs
    root.setLevel(log_level.upper())

    # Quiet down noisy third-party loggers so our own logs aren't drowned out.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)