"""Build dashboard/data.json — a read-only public snapshot. Never includes secrets."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from .alpaca_client import Account, Position
from .config import RISK, SETTINGS, WEIGHTS
from .decisions import Decision


_SCHEMA_VERSION = 1


def build_payload(
    account: Account | None,
    positions: list[Position],
    theme_summary: dict[str, dict],
    decisions: list[Decision],
    execution_results: list[dict],
    market_open: bool,
    cycle_count: int,
    last_success_iso: str | None,
    notes: list[str],
    equity_history: list[dict] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": _SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": "PAPER",
        "endpoint": "alpaca-paper",
        "cycle_count": cycle_count,
        "last_success_utc": last_success_iso,
        "market_open": market_open,
        "config": {
            "weights": {
                "momentum": WEIGHTS.momentum,
                "sentiment": WEIGHTS.sentiment,
                "volume": WEIGHTS.volume,
                "policy": WEIGHTS.policy,
            },
            "risk": {
                "max_theme_weight": RISK.max_theme_weight,
                "max_ticker_weight": RISK.max_ticker_weight,
                "max_new_buys_per_cycle": RISK.max_new_buys_per_cycle,
                "stop_loss_pct_range": [RISK.stop_loss_pct_min, RISK.stop_loss_pct_max],
                "min_price": RISK.min_price,
                "min_avg_daily_volume": RISK.min_avg_daily_volume,
                "reduce_below_score": RISK.reduce_below_score,
                "exit_below_score": RISK.exit_below_score,
                "cash_buffer_pct": RISK.cash_buffer_pct,
            },
            "min_run_interval_minutes": SETTINGS.min_run_interval_minutes,
        },
        "account": (
            {
                "equity": round(account.equity, 2),
                "cash": round(account.cash, 2),
                "buying_power": round(account.buying_power, 2),
                "portfolio_value": round(account.portfolio_value, 2),
            }
            if account
            else None
        ),
        "positions": [
            {
                "symbol": p.symbol,
                "qty": p.qty,
                "avg_entry_price": round(p.avg_entry_price, 4),
                "current_price": round(p.current_price, 4),
                "market_value": round(p.market_value, 2),
                "unrealized_pl": round(p.unrealized_pl, 2),
                "unrealized_plpc": round(p.unrealized_plpc, 4),
                "weight": round(p.market_value / account.equity, 4) if account and account.equity else 0.0,
            }
            for p in positions
        ],
        "themes": [
            {"key": k, **v} for k, v in sorted(theme_summary.items(), key=lambda kv: kv[1]["score"], reverse=True)
        ],
        "decisions": [d.to_dict() for d in decisions],
        "executions": execution_results,
        "equity_history": (equity_history or [])[-500:],
        "notes": notes,
    }


def write_dashboard(payload: dict[str, Any]) -> str:
    path = SETTINGS.dashboard_data_path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    os.replace(tmp, path)
    return path
