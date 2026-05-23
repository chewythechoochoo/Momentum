"""Apply decisions: place paper orders, attach stop-loss sells, log everything."""

from __future__ import annotations

from alpaca.trading.enums import OrderSide

from .alpaca_client import AlpacaPaperClient, Position
from .decisions import Decision
from .logger import get_logger, log_event
from .market_data import TickerFeatures
from .risk import stop_loss_price

log = get_logger(__name__)

# Don't submit dust orders ($5 minimum notional)
_MIN_NOTIONAL_USD = 5.00


def apply_decisions(
    client: AlpacaPaperClient,
    decisions: list[Decision],
    positions: list[Position],
    features: dict[str, TickerFeatures],
) -> list[dict]:
    pos_by_sym = {p.symbol: p for p in positions}
    results: list[dict] = []

    for d in decisions:
        if d.action in ("HOLD", "SKIP"):
            results.append({**d.to_dict(), "executed": False, "order": None})
            continue

        notional = abs(d.notional_delta)
        if notional < _MIN_NOTIONAL_USD:
            log_event(log, "order_skipped_dust", symbol=d.symbol, notional=notional)
            results.append({**d.to_dict(), "executed": False, "order": None,
                            "note": "dust_below_min_notional"})
            continue

        try:
            if d.action == "BUY":
                order = client.submit_market_order(d.symbol, notional, OrderSide.BUY)
                # Optionally attach a stop loss for new positions
                f = features.get(d.symbol)
                if order and f and f.valid and d.symbol not in pos_by_sym:
                    stop = stop_loss_price(f.last_price, f)
                    qty_est = notional / f.last_price if f.last_price > 0 else 0
                    if qty_est >= 1:
                        try:
                            client.submit_stop_loss(d.symbol, round(qty_est, 0), stop)
                        except Exception as e:  # noqa: BLE001
                            log_event(log, "stop_attach_failed", symbol=d.symbol, error=str(e))
                results.append({**d.to_dict(), "executed": bool(order), "order": order})

            elif d.action in ("SELL", "REDUCE"):
                order = client.submit_market_order(d.symbol, notional, OrderSide.SELL)
                results.append({**d.to_dict(), "executed": bool(order), "order": order})

        except Exception as e:  # noqa: BLE001
            log_event(log, "order_failed", symbol=d.symbol, action=d.action, error=str(e))
            results.append({**d.to_dict(), "executed": False, "order": None,
                            "error": str(e)})

    return results
