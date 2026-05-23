"""Risk filter & stop-loss tests."""

from __future__ import annotations

from src.config import RISK
from src.market_data import TickerFeatures
from src.risk import (
    cap_theme_weight,
    cap_ticker_weight,
    passes_liquidity,
    portfolio_drawdown_ok,
    stop_loss_price,
)


def _feat(**kw):
    base = dict(
        symbol="X", last_price=50.0, ret_1d=0, ret_5d=0, ret_20d=0,
        avg_volume_20d=5_000_000, rel_volume_5d=1.0,
        annualized_vol=0.30, rsi_14=50.0, valid=True,
    )
    base.update(kw)
    return TickerFeatures(**base)


def test_penny_stock_rejected():
    chk = passes_liquidity(_feat(last_price=3.50))
    assert not chk.ok and "price_below_floor" in chk.reason


def test_illiquid_rejected():
    chk = passes_liquidity(_feat(avg_volume_20d=200_000))
    assert not chk.ok and "illiquid" in chk.reason


def test_liquid_passes():
    assert passes_liquidity(_feat()).ok


def test_weight_caps():
    assert cap_ticker_weight(0.30) == RISK.max_ticker_weight
    assert cap_theme_weight(0.50) == RISK.max_theme_weight
    assert cap_ticker_weight(0.04) == 0.04


def test_stop_loss_widens_for_quiet_names():
    quiet = stop_loss_price(100.0, _feat(annualized_vol=0.15))
    noisy = stop_loss_price(100.0, _feat(annualized_vol=0.80))
    # Quieter name should have a *lower* stop price (wider stop → more room)
    assert quiet < noisy


def test_drawdown_halts_new_buys():
    chk = portfolio_drawdown_ok(80.0, 100.0)
    assert not chk.ok
    assert portfolio_drawdown_ok(95.0, 100.0).ok
