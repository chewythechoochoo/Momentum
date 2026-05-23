"""Structured stdout logger. Secrets are redacted via safety.redact() at call sites."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

from .config import SETTINGS


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        extras = getattr(record, "extras", None)
        if isinstance(extras, dict):
            payload.update(extras)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def get_logger(name: str = "trading-news-agent") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, SETTINGS.log_level, logging.INFO))
    logger.propagate = False
    return logger


def log_event(logger: logging.Logger, event: str, **fields) -> None:
    """Emit a structured event line."""
    logger.info(event, extra={"extras": {"event": event, **fields}})
