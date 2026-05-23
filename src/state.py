"""Persisted bot state — last run, recent decisions, cycle counter, daily PnL high-water mark."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from .config import SETTINGS


_DEFAULT_STATE: dict[str, Any] = {
    "schema_version": 2,
    "last_run_iso": None,
    "last_success_iso": None,
    "cycle_count": 0,
    "consecutive_errors": 0,
    "equity_high_water": None,
    "decision_log": [],     # ring buffer of last 200 decisions
    "equity_history": [],   # ring buffer of {"t": iso_utc, "v": equity}
}

_MAX_DECISION_LOG = 200
_MAX_EQUITY_HISTORY = 2000


def load_state() -> dict[str, Any]:
    path = SETTINGS.state_path
    if not os.path.exists(path):
        return dict(_DEFAULT_STATE)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return dict(_DEFAULT_STATE)
    # Forward-compatible merge
    merged = dict(_DEFAULT_STATE)
    merged.update(data)
    return merged


def save_state(state: dict[str, Any]) -> None:
    path = SETTINGS.state_path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, default=str)
    os.replace(tmp, path)


def append_decisions(state: dict[str, Any], decisions: list[dict[str, Any]]) -> None:
    log = state.setdefault("decision_log", [])
    log.extend(decisions)
    if len(log) > _MAX_DECISION_LOG:
        del log[: len(log) - _MAX_DECISION_LOG]


def mark_run_start(state: dict[str, Any]) -> None:
    state["last_run_iso"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    state["cycle_count"] = int(state.get("cycle_count", 0)) + 1


def mark_run_success(state: dict[str, Any], equity: float | None = None) -> None:
    state["last_success_iso"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    state["consecutive_errors"] = 0
    if equity is not None:
        hw = state.get("equity_high_water")
        if hw is None or equity > hw:
            state["equity_high_water"] = equity


def mark_run_error(state: dict[str, Any]) -> None:
    state["consecutive_errors"] = int(state.get("consecutive_errors", 0)) + 1


def append_equity(state: dict[str, Any], equity: float | None) -> None:
    """Append (now_utc, equity) to equity_history, trimming to the ring-buffer cap."""
    if equity is None or equity <= 0:
        return
    hist = state.setdefault("equity_history", [])
    hist.append({
        "t": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "v": round(float(equity), 2),
    })
    if len(hist) > _MAX_EQUITY_HISTORY:
        del hist[: len(hist) - _MAX_EQUITY_HISTORY]
