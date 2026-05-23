"""Scoring math: weights, score bands, volatility penalty."""

from __future__ import annotations

from src.market_data import TickerFeatures
from src.scoring import score_theme
from src.sentiment import SentimentResult
from src.themes import Theme


def _feat(sym: str, ret_5d=0.05, ret_20d=0.10, ret_1d=0.01, vol=0.30, rel_vol=1.2):
    return TickerFeatures(
        symbol=sym, last_price=100.0,
        ret_1d=ret_1d, ret_5d=ret_5d, ret_20d=ret_20d,
        avg_volume_20d=5_000_000, rel_volume_5d=rel_vol,
        annualized_vol=vol, rsi_14=60.0, valid=True,
    )


def _theme(*tickers: str) -> Theme:
    return Theme(key="t", name="Test", tickers=tickers, keywords=())


def test_bullish_theme_scores_high():
    theme = _theme("A", "B")
    feats = {"A": _feat("A"), "B": _feat("B")}
    sent = SentimentResult(score=0.6, positive_hits=10, negative_hits=2, policy_hits=2, sample_count=8)
    ts = score_theme(theme, feats, sent)
    assert ts.score > 60
    assert ts.momentum_component > 50
    assert ts.sentiment_component > 50
    assert 0 <= ts.confidence <= 1
    assert set(ts.valid_tickers) == {"A", "B"}


def test_bearish_features_score_low():
    theme = _theme("X")
    feats = {"X": _feat("X", ret_1d=-0.03, ret_5d=-0.06, ret_20d=-0.15, vol=0.80, rel_vol=0.5)}
    sent = SentimentResult(score=-0.7, positive_hits=1, negative_hits=8, policy_hits=0, sample_count=5)
    ts = score_theme(theme, feats, sent)
    assert ts.score < 40
    assert ts.volatility_penalty > 5


def test_no_valid_features_returns_neutral_ish():
    theme = _theme("Z")
    ts = score_theme(theme, {}, SentimentResult(0, 0, 0, 0, 0))
    assert 30 <= ts.score <= 70
    assert ts.valid_tickers == []
