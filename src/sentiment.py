"""Lightweight keyword sentiment + policy-catalyst detector. No external API calls."""

from __future__ import annotations

import re
from dataclasses import dataclass

_POSITIVE = {
    "surge", "soar", "rally", "beat", "beats", "tops", "record", "upgrade", "upgraded",
    "outperform", "strong", "growth", "expand", "approval", "approved", "wins", "win",
    "breakthrough", "launches", "raises", "raised", "boost", "boosted", "rebound",
    "bullish", "buy", "accelerates", "milestone", "partnership", "contract", "awarded",
    "subsidies", "subsidy", "tailwind", "outpaces", "demand", "blockbuster",
}

_NEGATIVE = {
    "miss", "missed", "plunge", "tumble", "downgrade", "downgraded", "underperform",
    "weak", "decline", "drop", "slump", "lawsuit", "probe", "investigation",
    "recall", "halts", "halt", "warning", "warns", "guidance cut", "layoffs", "fired",
    "delisting", "fraud", "subpoena", "bearish", "sell", "headwind", "shortfall",
    "bankrupt", "default", "restructure", "tariff", "ban", "banned",
}

# Words / phrases that indicate a *policy* catalyst (the 10% catalyst factor)
_POLICY_TERMS = {
    "executive order", "white house", "regulation", "regulatory", "subsidy",
    "subsidies", "tax credit", "infrastructure bill", "stimulus", "fed",
    "federal reserve", "rate cut", "rate hike", "tariff", "sanction", "epa",
    "sec ", "fda approval", "department of defense", "doe ", "irs ", "treasury",
    "doj", "antitrust", "ftc", "congress", "senate bill", "house bill",
}


@dataclass
class SentimentResult:
    score: float          # -1.0 .. +1.0
    positive_hits: int
    negative_hits: int
    policy_hits: int
    sample_count: int


def _hits(text: str, terms: set[str] | dict) -> int:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z\-]+", text.lower())
    token_set = set(tokens)
    single = sum(1 for t in terms if " " not in t and t in token_set)
    # Phrase matches (multi-word) — substring on lowered text
    lowered = text.lower()
    phrase = sum(1 for t in terms if " " in t and t in lowered)
    return single + phrase


def analyze(texts: list[str]) -> SentimentResult:
    if not texts:
        return SentimentResult(0.0, 0, 0, 0, 0)
    pos = neg = pol = 0
    for t in texts:
        if not t:
            continue
        pos += _hits(t, _POSITIVE)
        neg += _hits(t, _NEGATIVE)
        pol += _hits(t, _POLICY_TERMS)
    total = pos + neg
    if total == 0:
        score = 0.0
    else:
        score = (pos - neg) / total
    # Damp scores when only a tiny number of articles were analyzed
    confidence = min(1.0, len(texts) / 5.0)
    return SentimentResult(
        score=round(score * confidence, 4),
        positive_hits=pos,
        negative_hits=neg,
        policy_hits=pol,
        sample_count=len(texts),
    )
