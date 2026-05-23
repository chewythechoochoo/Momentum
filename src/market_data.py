"""Price / volume / volatility features built from Alpaca daily bars."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from .logger import get_logger, log_event

if TYPE_CHECKING:
    from .alpaca_client import AlpacaPaperClient

log = get_logger(__name__)


@dataclass
class TickerFeatures:
    symbol: str
    last_price: float
    ret_1d: float
    ret_5d: float
    ret_20d: float
    avg_volume_20d: float
    rel_volume_5d: float       # 5d avg / 20d avg
    annualized_vol: float      # std of daily log returns × sqrt(252)
    rsi_14: float
    valid: bool
    reason: str = ""


def _rsi(series: pd.Series, period: int = 14) -> float:
    if len(series) < period + 1:
        return float("nan")
    delta = series.diff().dropna()
    up = delta.clip(lower=0).rolling(period).mean().iloc[-1]
    down = (-delta.clip(upper=0)).rolling(period).mean().iloc[-1]
    if down == 0:
        return 100.0
    rs = up / down
    return float(100.0 - (100.0 / (1.0 + rs)))


def compute_features(client: "AlpacaPaperClient", symbols: list[str]) -> dict[str, TickerFeatures]:
    if not symbols:
        return {}
    end = datetime.now(timezone.utc) - timedelta(minutes=20)  # avoid SIP delay
    start = end - timedelta(days=60)
    try:
        bars = client.get_bars(symbols, start=start, end=end)
    except Exception as e:  # noqa: BLE001
        log_event(log, "bars_fetch_failed", error=str(e), symbols=symbols)
        return {s: TickerFeatures(s, 0, 0, 0, 0, 0, 0, 0, 0, False, f"bars_error: {e}") for s in symbols}

    out: dict[str, TickerFeatures] = {}
    if bars is None or bars.empty:
        for s in symbols:
            out[s] = TickerFeatures(s, 0, 0, 0, 0, 0, 0, 0, 0, False, "no_bars")
        return out

    # alpaca-py returns a MultiIndex (symbol, timestamp)
    for sym in symbols:
        try:
            df = bars.xs(sym, level=0) if sym in bars.index.get_level_values(0) else None
        except (KeyError, IndexError):
            df = None
        if df is None or df.empty or len(df) < 6:
            out[sym] = TickerFeatures(sym, 0, 0, 0, 0, 0, 0, 0, 0, False, "insufficient_history")
            continue

        df = df.sort_index()
        close = df["close"].astype(float)
        vol = df["volume"].astype(float)
        last = float(close.iloc[-1])

        def _ret(n: int) -> float:
            if len(close) <= n:
                return 0.0
            return float(close.iloc[-1] / close.iloc[-1 - n] - 1.0)

        log_ret = np.log(close / close.shift(1)).dropna()
        annualized_vol = float(log_ret.std() * np.sqrt(252)) if len(log_ret) > 5 else 0.0

        avg_vol_20 = float(vol.tail(20).mean())
        avg_vol_5 = float(vol.tail(5).mean())
        rel_vol = avg_vol_5 / avg_vol_20 if avg_vol_20 > 0 else 1.0

        out[sym] = TickerFeatures(
            symbol=sym,
            last_price=last,
            ret_1d=_ret(1),
            ret_5d=_ret(5),
            ret_20d=_ret(20),
            avg_volume_20d=avg_vol_20,
            rel_volume_5d=rel_vol,
            annualized_vol=annualized_vol,
            rsi_14=_rsi(close),
            valid=True,
        )
    return out
