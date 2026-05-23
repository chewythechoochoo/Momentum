"""Entry point — one trading cycle. Invoked by the GitHub Actions cron every 15 minutes.

Flow:
  1. Pre-flight safety (paper-only, credentials, min-interval).
  2. Fetch account + positions.
  3. For each theme: fetch features + news, score it.
  4. Build target allocations and decisions.
  5. If market is open: execute. Otherwise: dry-run.
  6. Write dashboard/data.json. Persist state.
"""

from __future__ import annotations

import sys
import traceback
from datetime import datetime, timezone

from .alpaca_client import AlpacaPaperClient
from .allocator import build_targets
from .decisions import build_decisions
from .executor import apply_decisions
from .logger import get_logger, log_event
from .market_data import compute_features
from .news import fetch_news_for_symbols
from .reporter import build_payload, write_dashboard
from .safety import SafetyError, assert_min_interval, redact
from .scoring import score_theme
from .sentiment import analyze
from .state import (
    append_decisions,
    load_state,
    mark_run_error,
    mark_run_start,
    mark_run_success,
    save_state,
)
from .themes import THEMES, all_tickers

log = get_logger("trading-news-agent.main")


def run_cycle() -> int:
    state = load_state()
    notes: list[str] = []

    try:
        assert_min_interval(state.get("last_success_iso"))
    except SafetyError as e:
        log_event(log, "min_interval_violation", error=str(e))
        notes.append(str(e))
        # Still update the dashboard with the note, then exit 0 (not a failure).
        _write_minimal_dashboard(notes)
        return 0

    mark_run_start(state)
    save_state(state)

    try:
        client = AlpacaPaperClient()
        log_event(
            log,
            "preflight_ok",
            key=redact(client.trading._api_key),
            endpoint=client.paper_endpoint,
        )
    except SafetyError as e:
        log_event(log, "preflight_failed", error=str(e))
        notes.append(f"preflight failed: {e}")
        _write_minimal_dashboard(notes)
        return 2

    market_open = False
    account = None
    positions = []
    try:
        market_open = client.is_market_open()
        account = client.get_account()
        positions = client.get_positions()
    except Exception as e:  # noqa: BLE001
        log_event(log, "account_fetch_failed", error=str(e))
        notes.append(f"account fetch failed: {e}")

    # --- Score every theme ---
    symbols = all_tickers()
    features = compute_features(client, symbols)

    theme_scores = []
    for theme in THEMES:
        theme_syms = list(theme.tickers)
        news = fetch_news_for_symbols(theme_syms, keywords=" OR ".join(theme.keywords))
        texts = [(n.headline or "") + ". " + (n.summary or "") for n in news]
        sentiment = analyze(texts)
        ts = score_theme(theme, features, sentiment)
        theme_scores.append(ts)
        log_event(
            log, "theme_scored",
            theme=theme.key, score=ts.score, confidence=ts.confidence,
            news_count=len(news),
        )

    # --- Allocate ---
    targets, theme_summary = build_targets(theme_scores, features)

    # --- Decide ---
    equity = account.equity if account else 0.0
    decisions = build_decisions(
        targets, theme_scores, positions, features,
        equity=equity,
        equity_high_water=state.get("equity_high_water"),
    )
    log_event(log, "decisions_built", count=len(decisions))

    # --- Execute (only when market is open) ---
    execution_results: list[dict] = []
    if market_open and account is not None:
        execution_results = apply_decisions(client, decisions, positions, features)
    else:
        # Dry-run: mark every decision as not executed but still report
        for d in decisions:
            execution_results.append({**d.to_dict(), "executed": False, "order": None,
                                      "note": "market_closed_or_no_account"})
        if not market_open:
            notes.append("Market is closed — decisions are advisory; no orders placed.")

    # --- Reporter writes the dashboard ---
    payload = build_payload(
        account=account,
        positions=positions,
        theme_summary=theme_summary,
        decisions=decisions,
        execution_results=execution_results,
        market_open=market_open,
        cycle_count=state.get("cycle_count", 0),
        last_success_iso=state.get("last_success_iso"),
        notes=notes,
    )
    path = write_dashboard(payload)
    log_event(log, "dashboard_written", path=path)

    # --- Persist state ---
    append_decisions(state, [d.to_dict() for d in decisions])
    mark_run_success(state, equity=equity if equity > 0 else None)
    save_state(state)
    return 0


def _write_minimal_dashboard(notes: list[str]) -> None:
    payload = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": "PAPER",
        "account": None,
        "positions": [],
        "themes": [],
        "decisions": [],
        "executions": [],
        "notes": notes,
    }
    try:
        write_dashboard(payload)
    except Exception:  # noqa: BLE001
        pass


def main() -> int:
    try:
        return run_cycle()
    except SafetyError as e:
        log_event(log, "safety_error", error=str(e))
        print(f"SAFETY ABORT: {e}", file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001
        state = load_state()
        mark_run_error(state)
        save_state(state)
        log_event(log, "cycle_unhandled_error", error=str(e), trace=traceback.format_exc())
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
