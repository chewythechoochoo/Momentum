"""Risk filters and stop-loss math. Anything that violates these rules is rejected by the executor."""

from __future__ import annotations

from dataclasses import dataclass

from .config import RISK
from .market_data import TickerFeatures


@dataclass
class RiskCheck:
    ok: bool
    reason: str = ""


def passes_liquidity(f: TickerFeatures) -> RiskCheck:
    if not f.valid:
        return RiskCheck(False, f"no_valid_features:{f.reason}")
    if f.last_price < RISK.min_price:
        return RiskCheck(False, f"price_below_floor ({f.last_price:.2f} < ${RISK.min_price})")
    if f.avg_volume_20d < RISK.min_avg_daily_volume:
        return RiskCheck(False, f"illiquid (20d avg vol {f.avg_volume_20d:,.0f})")
    return RiskCheck(True)


def cap_ticker_weight(target_weight: float) -> float:
    return min(target_weight, RISK.max_ticker_weight)


def cap_theme_weight(target_weight: float) -> float:
    return min(target_weight, RISK.max_theme_weight)


def stop_loss_price(entry_price: float, f: TickerFeatures) -> float:
    """Pick a 5–8% stop based on annualized volatility.

    Quieter names get an 8% stop (more room); high-vol names get tightened to 5%.
    """
    if f.annualized_vol >= 0.60:
        pct = RISK.stop_loss_pct_min
    elif f.annualized_vol >= 0.40:
        pct = (RISK.stop_loss_pct_min + RISK.stop_loss_pct) / 2.0
    elif f.annualized_vol >= 0.25:
        pct = RISK.stop_loss_pct
    else:
        pct = RISK.stop_loss_pct_max
    return round(entry_price * (1.0 - pct), 2)


def portfolio_drawdown_ok(current_equity: float, high_water: float | None) -> RiskCheck:
    if high_water is None or high_water <= 0:
        return RiskCheck(True)
    dd = (high_water - current_equity) / high_water
    if dd > RISK.max_portfolio_drawdown_pct:
        return RiskCheck(
            False,
            f"portfolio_drawdown {dd:.1%} exceeds limit {RISK.max_portfolio_drawdown_pct:.0%}",
        )
    return RiskCheck(True)
