"""Map theme scores → target dollar weights, then split each theme's weight across its top tickers."""

from __future__ import annotations

from dataclasses import dataclass

from .config import RISK, SCORE_BANDS
from .market_data import TickerFeatures
from .risk import cap_theme_weight, cap_ticker_weight, passes_liquidity
from .scoring import ThemeScore


@dataclass
class TickerTarget:
    symbol: str
    theme_key: str
    target_weight: float       # portfolio fraction (0..1)
    reason: str
    contribution_score: float


def _band_for(score: float):
    for b in SCORE_BANDS:
        if b.min_score <= score < b.max_score:
            return b
    return SCORE_BANDS[-1]


def _theme_target_weight(theme: ThemeScore) -> tuple[float, str]:
    band = _band_for(theme.score)
    if band.target_max == 0:
        return 0.0, band.label
    # Interpolate within the band based on where in the band the score falls.
    span = max(band.max_score - band.min_score, 0.01)
    pos = (theme.score - band.min_score) / span
    raw = band.target_min + pos * (band.target_max - band.target_min)
    # Scale by confidence — low-data themes get a smaller allocation
    adjusted = raw * (0.5 + 0.5 * theme.confidence)
    return cap_theme_weight(adjusted), band.label


def build_targets(
    theme_scores: list[ThemeScore],
    features: dict[str, TickerFeatures],
    max_tickers_per_theme: int = 3,
) -> tuple[list[TickerTarget], dict[str, dict]]:
    """Return per-ticker targets and a per-theme summary dict for the dashboard."""
    targets: list[TickerTarget] = []
    theme_summary: dict[str, dict] = {}
    total_theme_weight = 0.0

    # Sort themes by score descending so caps bind to strongest themes first
    sorted_themes = sorted(theme_scores, key=lambda t: t.score, reverse=True)

    for ts in sorted_themes:
        weight, band_label = _theme_target_weight(ts)
        theme_summary[ts.theme_key] = {
            "name": ts.theme_name,
            "score": ts.score,
            "raw_score": ts.raw_score,
            "band": band_label,
            "weight": round(weight, 4),
            "confidence": ts.confidence,
            "components": {
                "momentum": ts.momentum_component,
                "sentiment": ts.sentiment_component,
                "volume": ts.volume_component,
                "policy": ts.policy_component,
                "volatility_penalty": ts.volatility_penalty,
            },
        }
        if weight <= 0:
            continue

        # Enforce overall cap: total of all theme weights ≤ 1 - cash_buffer
        remaining = max(0.0, (1.0 - RISK.cash_buffer_pct) - total_theme_weight)
        weight = min(weight, remaining)
        if weight <= 0:
            continue
        total_theme_weight += weight

        # Pick top tickers by per-ticker contribution score, filtering for liquidity
        candidates = sorted(
            ts.contributions.items(), key=lambda kv: kv[1], reverse=True
        )
        chosen: list[tuple[str, float]] = []
        for sym, contrib in candidates:
            f = features.get(sym)
            if not f:
                continue
            chk = passes_liquidity(f)
            if not chk.ok:
                continue
            chosen.append((sym, contrib))
            if len(chosen) >= max_tickers_per_theme:
                break

        if not chosen:
            continue

        # Split theme weight proportionally to contribution
        total_contrib = sum(c for _, c in chosen) or 1.0
        for sym, contrib in chosen:
            raw_w = weight * (contrib / total_contrib)
            capped = cap_ticker_weight(raw_w)
            if capped < RISK.min_ticker_weight:
                continue
            targets.append(
                TickerTarget(
                    symbol=sym,
                    theme_key=ts.theme_key,
                    target_weight=round(capped, 4),
                    reason=f"theme '{ts.theme_name}' score {ts.score:.1f} ({band_label}), "
                    f"contribution {contrib:.1f}",
                    contribution_score=contrib,
                )
            )

    return targets, theme_summary
