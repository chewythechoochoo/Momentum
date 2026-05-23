"""Pre-flight safety checks. Anything that could enable real-money trading hard-fails here."""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import ALPACA_PAPER_ENDPOINT, SETTINGS


class SafetyError(RuntimeError):
    """Raised when a hard safety invariant is violated. Always fatal — do not catch."""


_REAL_MONEY_SUBSTRINGS = (
    "api.alpaca.markets",  # live trading endpoint
    "live-api",
    "live.alpaca",
)


def assert_paper_only() -> str:
    """Verify we're running against the Alpaca paper endpoint. Returns the endpoint URL."""
    if not SETTINGS.alpaca_paper:
        raise SafetyError(
            "ALPACA_PAPER is not 'true'. This bot refuses to run against any non-paper "
            "configuration. Remove ALPACA_PAPER=false and try again."
        )

    override = SETTINGS.alpaca_base_url_override
    if override:
        normalized = override.lower()
        if any(s in normalized for s in _REAL_MONEY_SUBSTRINGS):
            raise SafetyError(
                f"ALPACA_BASE_URL='{override}' points at a live-money endpoint. Refusing to start."
            )
        if "paper" not in normalized:
            raise SafetyError(
                f"ALPACA_BASE_URL='{override}' is not recognizably a paper endpoint. Refusing."
            )
        return override

    return ALPACA_PAPER_ENDPOINT


def assert_credentials_present() -> None:
    if not SETTINGS.alpaca_key or not SETTINGS.alpaca_secret:
        raise SafetyError(
            "ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY must both be set (paper keys only)."
        )
    # Alpaca paper keys begin with "PK"; live keys begin with "AK". Reject AK loudly.
    if SETTINGS.alpaca_key.upper().startswith("AK"):
        raise SafetyError(
            "Provided ALPACA_API_KEY_ID looks like a LIVE key (starts with 'AK'). "
            "This bot only accepts paper keys (typically prefixed 'PK')."
        )


def assert_min_interval(last_run_iso: str | None) -> None:
    """Refuse to run if the last successful cycle was less than MIN_RUN_INTERVAL_MINUTES ago."""
    if not last_run_iso:
        return
    try:
        last = datetime.fromisoformat(last_run_iso)
    except ValueError:
        return
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    elapsed = now - last
    floor = timedelta(minutes=SETTINGS.min_run_interval_minutes)
    if elapsed < floor:
        remaining = (floor - elapsed).total_seconds()
        raise SafetyError(
            f"Last cycle was {int(elapsed.total_seconds())}s ago; minimum interval is "
            f"{SETTINGS.min_run_interval_minutes}m. Sleep {int(remaining)}s before retrying."
        )


def redact(value: str | None, keep: int = 4) -> str:
    """Mask secrets for safe logging."""
    if not value:
        return "<unset>"
    if len(value) <= keep:
        return "*" * len(value)
    return value[:keep] + "*" * (len(value) - keep)


def run_preflight() -> str:
    """Run all safety checks. Returns the validated paper endpoint URL."""
    endpoint = assert_paper_only()
    assert_credentials_present()
    return endpoint
