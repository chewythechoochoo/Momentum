"""Theme scoring: 40% momentum, 30% sentiment, 20% volume, 10% policy catalyst.

All sub-scores are normalized to 0..100 BEFORE weighting. A volatility penalty
is subtracted after weighting. A confidence score (0..1) accompanies each theme
score and is used downstream by the allocator to scale target weights.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import mean

from .config import WEIGHTS
from .market_data import TickerFeatures
from .sentiment import SentimentResult
from .themes import Theme


@dataclass
class ThemeScore:
    theme_key: str
    theme_name: str
    score: float                  # 0..100 final score (after vol penalty)
    raw_score: float              # 0..100 before vol penalty
    momentum_component: float     # 0..100
    sentiment_component: float    # 0..100
    volume_component: float       # 0..100
    policy_component: float       # 0..100
    volatility_penalty: float     # 0..30
    confidence: float             # 0..1
    valid_tickers: list[str] = field(default_factory=list)
    contributions: dict[str, float] = field(default_factory=dict)  # per-ticker scores


def _clip(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _momentum_score(feats: list[TickerFeatures]) -> float:
    """Blend 1d/5d/20d returns into a 0..100 score.

    Returns of +5%/+10%/+20% on the three horizons land near 100.
    Returns of -5%/-10%/-20% land near 0. Linear in log returns for stability.
    """
    if not feats:
        return 50.0

    def _ret_to_score(r: float, target_pct: float) -> float:
        # +target → 100, -target → 0, 0 → 50.
        return _clip(50.0 + (r / (target_pct / 100.0)) * 50.0)

    s1 = mean(_ret_to_score(f.ret_1d, 2.0) for f in feats)
    s5 = mean(_ret_to_score(f.ret_5d, 5.0) for f in feats)
    s20 = mean(_ret_to_score(f.ret_20d, 12.0) for f in feats)
    # Recent momentum weighted slightly more
    return _clip(0.45 * s5 + 0.35 * s20 + 0.20 * s1)


def _volume_score(feats: list[TickerFeatures]) -> float:
    """5d / 20d volume ratio. Ratio of 1.0 → 50, 1.5 → ~85, 2.0+ → 100."""
    if not feats:
        return 50.0
    ratios = [f.rel_volume_5d for f in feats if f.rel_volume_5d > 0]
    if not ratios:
        return 50.0
    r = mean(ratios)
    # logistic-ish map
    return _clip(50.0 + math.log(max(r, 0.25)) * 60.0)


def _sentiment_score(s: SentimentResult) -> float:
    """Map -1..+1 sentiment to 0..100, with neutral at 50."""
    return _clip(50.0 + s.score * 50.0)


def _policy_score(s: SentimentResult) -> float:
    """0 hits → 50, scaling up to 100 around 5+ catalyst mentions."""
    if s.policy_hits <= 0:
        return 50.0
    return _clip(50.0 + min(s.policy_hits, 10) * 5.0)


def _volatility_penalty(feats: list[TickerFeatures]) -> float:
    """Penalize themes whose constituents are highly volatile. 0..30 points."""
    if not feats:
        return 0.0
    vols = [f.annualized_vol for f in feats if f.annualized_vol > 0]
    if not vols:
        return 0.0
    v = mean(vols)
    # 40% vol → ~10pt penalty, 80% vol → ~25pt, 120%+ → cap at 30
    return _clip(max(0.0, (v - 0.30)) * 35.0, 0.0, 30.0)


def _confidence(feats: list[TickerFeatures], sentiment: SentimentResult) -> float:
    valid_share = sum(1 for f in feats if f.valid) / max(len(feats), 1)
    news_factor = min(1.0, sentiment.sample_count / 8.0)
    return round(0.6 * valid_share + 0.4 * news_factor, 3)


def score_theme(
    theme: Theme,
    feats: dict[str, TickerFeatures],
    sentiment: SentimentResult,
) -> ThemeScore:
    valid = [feats[t] for t in theme.tickers if t in feats and feats[t].valid]
    valid_syms = [f.symbol for f in valid]

    momentum = _momentum_score(valid)
    sentiment_c = _sentiment_score(sentiment)
    volume = _volume_score(valid)
    policy = _policy_score(sentiment)

    raw = (
        WEIGHTS.momentum * momentum
        + WEIGHTS.sentiment * sentiment_c
        + WEIGHTS.volume * volume
        + WEIGHTS.policy * policy
    )
    penalty = _volatility_penalty(valid)
    final = _clip(raw - penalty)

    # Per-ticker contribution (used by allocator to pick winners within the theme)
    contributions: dict[str, float] = {}
    for f in valid:
        s = (
            WEIGHTS.momentum * _clip(50.0 + (f.ret_5d / 0.05) * 50.0)
            + WEIGHTS.volume * _clip(50.0 + math.log(max(f.rel_volume_5d, 0.25)) * 60.0)
            + WEIGHTS.sentiment * sentiment_c
            + WEIGHTS.policy * policy
        )
        # Per-ticker penalty
        s -= _clip(max(0.0, (f.annualized_vol - 0.30)) * 35.0, 0.0, 30.0)
        contributions[f.symbol] = round(_clip(s), 2)

    return ThemeScore(
        theme_key=theme.key,
        theme_name=theme.name,
        score=round(final, 2),
        raw_score=round(raw, 2),
        momentum_component=round(momentum, 2),
        sentiment_component=round(sentiment_c, 2),
        volume_component=round(volume, 2),
        policy_component=round(policy, 2),
        volatility_penalty=round(penalty, 2),
        confidence=_confidence(valid, sentiment),
        valid_tickers=valid_syms,
        contributions=contributions,
    )
