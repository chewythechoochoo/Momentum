"""Diff target weights vs. current positions → human-readable buy/sell/hold/skip decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .alpaca_client import Position
from .allocator import TickerTarget
from .config import RISK
from .market_data import TickerFeatures
from .risk import passes_liquidity, portfolio_drawdown_ok
from .scoring import ThemeScore

Action = Literal["BUY", "SELL", "REDUCE", "HOLD", "SKIP"]


@dataclass
class Decision:
    symbol: str
    action: Action
    target_weight: float
    current_weight: float
    notional_delta: float           # +ve buy, -ve sell (in $)
    reason: str
    factors: list[str] = field(default_factory=list)
    theme_key: str = ""

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "action": self.action,
            "target_weight": round(self.target_weight, 4),
            "current_weight": round(self.current_weight, 4),
            "notional_delta": round(self.notional_delta, 2),
            "reason": self.reason,
            "factors": self.factors,
            "theme_key": self.theme_key,
        }


def _current_weight(symbol: str, positions: list[Position], equity: float) -> float:
    if equity <= 0:
        return 0.0
    for p in positions:
        if p.symbol == symbol:
            return p.market_value / equity
    return 0.0


def build_decisions(
    targets: list[TickerTarget],
    theme_scores: list[ThemeScore],
    positions: list[Position],
    features: dict[str, TickerFeatures],
    equity: float,
    equity_high_water: float | None,
) -> list[Decision]:
    target_map = {t.symbol: t for t in targets}
    theme_map = {t.theme_key: t for t in theme_scores}
    decisions: list[Decision] = []

    dd_check = portfolio_drawdown_ok(equity, equity_high_water)
    halt_new_buys = not dd_check.ok

    # 1) Existing positions: hold / reduce / sell based on theme score and weight diff
    held_syms = {p.symbol for p in positions}
    for p in positions:
        target = target_map.get(p.symbol)
        cur_w = p.market_value / equity if equity > 0 else 0.0

        # Theme this position belongs to (find by membership)
        owning_theme_key = target.theme_key if target else _find_theme(p.symbol, theme_scores)
        owning_theme = theme_map.get(owning_theme_key) if owning_theme_key else None

        factors = [
            f"unrealized_pl={p.unrealized_plpc:.2%}",
            f"theme={owning_theme.theme_name if owning_theme else 'unknown'}",
        ]

        # Force-exit if theme score collapsed
        if owning_theme and owning_theme.score < RISK.exit_below_score:
            decisions.append(Decision(
                symbol=p.symbol, action="SELL",
                target_weight=0.0, current_weight=cur_w,
                notional_delta=-p.market_value,
                reason=f"theme score {owning_theme.score:.1f} < exit threshold "
                       f"{RISK.exit_below_score:.0f} — fully exit",
                factors=factors,
                theme_key=owning_theme_key or "",
            ))
            continue

        # Reduce if theme score is weak
        if owning_theme and owning_theme.score < RISK.reduce_below_score:
            target_w = cur_w * 0.5
            decisions.append(Decision(
                symbol=p.symbol, action="REDUCE",
                target_weight=target_w, current_weight=cur_w,
                notional_delta=-(p.market_value * 0.5),
                reason=f"theme score {owning_theme.score:.1f} < reduce threshold "
                       f"{RISK.reduce_below_score:.0f} — halve position",
                factors=factors,
                theme_key=owning_theme_key or "",
            ))
            continue

        if target is None:
            # Held but not in current target set — taper to zero
            decisions.append(Decision(
                symbol=p.symbol, action="SELL",
                target_weight=0.0, current_weight=cur_w,
                notional_delta=-p.market_value,
                reason="no longer in target set — exit",
                factors=factors,
                theme_key=owning_theme_key or "",
            ))
            continue

        diff = target.target_weight - cur_w
        notional_delta = diff * equity
        if abs(diff) < 0.005:  # within 50bps — leave alone
            decisions.append(Decision(
                symbol=p.symbol, action="HOLD",
                target_weight=target.target_weight, current_weight=cur_w,
                notional_delta=0.0,
                reason="within 50bps of target — no trade",
                factors=factors + [target.reason],
                theme_key=target.theme_key,
            ))
        elif diff < 0:
            decisions.append(Decision(
                symbol=p.symbol, action="REDUCE",
                target_weight=target.target_weight, current_weight=cur_w,
                notional_delta=notional_delta,
                reason=f"overweight by {-diff:.2%} vs target — trim",
                factors=factors + [target.reason],
                theme_key=target.theme_key,
            ))
        else:
            # Adding to existing position
            decisions.append(Decision(
                symbol=p.symbol, action="BUY",
                target_weight=target.target_weight, current_weight=cur_w,
                notional_delta=notional_delta,
                reason=f"underweight by {diff:.2%} vs target — add",
                factors=factors + [target.reason],
                theme_key=target.theme_key,
            ))

    # 2) New positions not currently held
    new_buy_candidates: list[Decision] = []
    for t in targets:
        if t.symbol in held_syms:
            continue
        f = features.get(t.symbol)
        factors = []
        if f:
            factors = [
                f"ret_5d={f.ret_5d:.2%}",
                f"rel_vol_5d={f.rel_volume_5d:.2f}",
                f"vol_ann={f.annualized_vol:.2%}",
            ]
        chk = passes_liquidity(f) if f else None
        if chk and not chk.ok:
            new_buy_candidates.append(Decision(
                symbol=t.symbol, action="SKIP",
                target_weight=t.target_weight, current_weight=0.0,
                notional_delta=0.0,
                reason=f"risk filter: {chk.reason}",
                factors=factors,
                theme_key=t.theme_key,
            ))
            continue
        if halt_new_buys:
            new_buy_candidates.append(Decision(
                symbol=t.symbol, action="SKIP",
                target_weight=t.target_weight, current_weight=0.0,
                notional_delta=0.0,
                reason=f"new buys halted: {dd_check.reason}",
                factors=factors,
                theme_key=t.theme_key,
            ))
            continue
        notional = t.target_weight * equity
        new_buy_candidates.append(Decision(
            symbol=t.symbol, action="BUY",
            target_weight=t.target_weight, current_weight=0.0,
            notional_delta=notional,
            reason=f"new position — {t.reason}",
            factors=factors,
            theme_key=t.theme_key,
        ))

    # Cap new buys per cycle (rank by contribution score)
    sortable = [(target_map.get(d.symbol).contribution_score if target_map.get(d.symbol) else 0.0, d)
                for d in new_buy_candidates if d.action == "BUY"]
    sortable.sort(key=lambda x: x[0], reverse=True)
    allowed = {d.symbol for _, d in sortable[: RISK.max_new_buys_per_cycle]}
    for d in new_buy_candidates:
        if d.action == "BUY" and d.symbol not in allowed:
            d.action = "SKIP"
            d.reason = (f"deferred — already at max {RISK.max_new_buys_per_cycle} "
                        f"new buys this cycle ({d.reason})")
            d.notional_delta = 0.0
        decisions.append(d)

    return decisions


def _find_theme(symbol: str, theme_scores: list[ThemeScore]) -> str | None:
    from .themes import THEMES
    for theme in THEMES:
        if symbol in theme.tickers:
            return theme.key
    return None
