"""Safety preflight tests — make sure live-money configs are refused."""

from __future__ import annotations

import importlib
import os

import pytest


def _reload_safety(env: dict):
    for k in ("ALPACA_API_KEY_ID", "ALPACA_API_SECRET_KEY", "ALPACA_PAPER", "ALPACA_BASE_URL"):
        os.environ.pop(k, None)
    os.environ.update(env)
    import src.config as cfg  # noqa: WPS433
    import src.safety as safety  # noqa: WPS433
    importlib.reload(cfg)
    importlib.reload(safety)
    return safety


def test_live_endpoint_refused():
    safety = _reload_safety({
        "ALPACA_API_KEY_ID": "PKTEST", "ALPACA_API_SECRET_KEY": "secret",
        "ALPACA_PAPER": "true", "ALPACA_BASE_URL": "https://api.alpaca.markets",
    })
    with pytest.raises(safety.SafetyError):
        safety.assert_paper_only()


def test_alpaca_paper_false_refused():
    safety = _reload_safety({
        "ALPACA_API_KEY_ID": "PKTEST", "ALPACA_API_SECRET_KEY": "secret",
        "ALPACA_PAPER": "false",
    })
    with pytest.raises(safety.SafetyError):
        safety.assert_paper_only()


def test_live_key_prefix_refused():
    safety = _reload_safety({
        "ALPACA_API_KEY_ID": "AKLIVEKEY", "ALPACA_API_SECRET_KEY": "secret",
        "ALPACA_PAPER": "true",
    })
    with pytest.raises(safety.SafetyError):
        safety.assert_credentials_present()


def test_paper_endpoint_accepted():
    safety = _reload_safety({
        "ALPACA_API_KEY_ID": "PKTEST", "ALPACA_API_SECRET_KEY": "secret",
        "ALPACA_PAPER": "true",
    })
    endpoint = safety.assert_paper_only()
    assert "paper" in endpoint


def test_min_interval_guardrail():
    safety = _reload_safety({
        "ALPACA_API_KEY_ID": "PKTEST", "ALPACA_API_SECRET_KEY": "secret",
        "ALPACA_PAPER": "true", "MIN_RUN_INTERVAL_MINUTES": "14",
    })
    from datetime import datetime, timezone, timedelta
    recent = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    with pytest.raises(safety.SafetyError):
        safety.assert_min_interval(recent)
    old = (datetime.now(timezone.utc) - timedelta(minutes=60)).isoformat()
    safety.assert_min_interval(old)  # should not raise
