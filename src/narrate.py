"""Turn the bot's terse internal reasons into human-readable narratives.

Given the decision and any recent news headlines mentioning the ticker,
classify the most-relevant headline by event type (earnings, M&A, FDA,
contract win, lawsuit, etc.) and weave that into a one-line story like:

    BUY — earnings beat: "NVDA tops Q1 estimates as datacenter ..."
    SELL — FDA rejection: "Lilly Phase III drug fails endpoints"
    HOLD — within 50bps of target, no fresh catalyst this cycle
    SKIP — at max 2 new buys this cycle; next priority CRWD (strong_buy)

No external APIs. Pattern-matching against the news.NewsItem stream the
bot already pulls per theme.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

# Order matters — the first matching pattern wins.
# Each entry: (event label, list of substrings to search lowercased headline+summary)
_EVENT_PATTERNS: list[tuple[str, list[str]]] = [
    ("M&A",                ["acquires", "acquired by", "acquisition of", "merger with",
                            "to acquire", "buyout", "takeover"]),
    ("earnings beat",      ["tops estimates", "beats estimates", "beats expectations",
                            "earnings beat", "raises guidance", "raises full-year",
                            "blowout quarter"]),
    ("earnings miss",      ["misses estimates", "misses expectations", "earnings miss",
                            "cuts guidance", "guidance cut", "lower-than-expected",
                            "missed q"]),
    ("FDA approval",       ["fda approval", "fda approves", "approved by fda",
                            "regulatory approval"]),
    ("FDA rejection",      ["fda rejection", "fda rejects", "rejected by fda",
                            "complete response letter", "trial failed", "missed endpoints"]),
    ("trial data",         ["clinical trial", "phase iii", "phase 3 trial", "topline data",
                            "drug study", "trial results"]),
    ("analyst upgrade",    ["upgraded to buy", "raised price target", "upgraded by",
                            "outperform rating", "raised to overweight"]),
    ("analyst downgrade",  ["downgraded to", "cut price target", "lowered price target",
                            "downgraded by", "cut to underweight"]),
    ("contract win",       ["awarded contract", "wins contract", "$ contract",
                            "selected by", "won a deal", "secures order"]),
    ("policy tailwind",    ["subsidy", "tax credit", "infrastructure bill", "stimulus",
                            "executive order", "ira tax credit"]),
    ("policy headwind",    ["tariff", "export ban", "sanction", "antitrust",
                            "regulatory probe"]),
    ("legal risk",         ["lawsuit", "class action", "subpoena", "indictment",
                            "investigation", "doj probe"]),
    ("recall",             ["product recall", "issues recall", "recalls"]),
    ("data breach",        ["data breach", "ransomware attack", "cyberattack on",
                            "breach affected"]),
    ("supply shock",       ["supply chain", "chip shortage", "shortage of",
                            "production halt", "factory fire"]),
    ("guidance raise",     ["raises outlook", "raises forecast", "lifts forecast"]),
    ("buyback",            ["share buyback", "stock repurchase", "buyback program"]),
    ("dividend",           ["increases dividend", "raises dividend", "special dividend"]),
    ("export news",        ["export controls", "export restrictions", "exports surged",
                            "export ban"]),
    ("layoffs",            ["layoffs", "cuts jobs", "job cuts", "workforce reduction"]),
    ("partnership",        ["announces partnership", "strategic partnership",
                            "joint venture"]),
]


@dataclass
class NewsHit:
    headline: str
    sentiment: float
    published_iso: str
    source: str
    url: str
    event: str | None


def _classify(text: str) -> str | None:
    """Word-bag match: all words in a pattern must appear in the headline
    (in any order, possibly with words in between). Single-word patterns
    behave like a substring match on whole tokens."""
    tokens = set(_tokenize(text))
    for label, patterns in _EVENT_PATTERNS:
        for p in patterns:
            words = p.lower().split()
            if all(w.strip("$.,:;\"'") in tokens for w in words):
                return label
    return None


def _tokenize(text: str) -> list[str]:
    import re
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if t]


def pick_best_hit(news_for_ticker: list[dict]) -> NewsHit | None:
    """From a ticker's news list, pick the strongest-signal headline.

    Ranks by |sentiment| × recency. Returns None if list is empty.
    """
    if not news_for_ticker:
        return None
    # Recency: newest first
    items = sorted(news_for_ticker,
                   key=lambda n: n.get("published_utc", ""), reverse=True)
    # Among the 6 most recent, pick the one with strongest sentiment.
    pool = items[:6]
    best = max(pool, key=lambda n: abs(float(n.get("sentiment_score", 0) or 0)))
    text = (best.get("headline") or "") + ". " + (best.get("summary") or "")
    return NewsHit(
        headline=best.get("headline", "") or "",
        sentiment=float(best.get("sentiment_score", 0) or 0),
        published_iso=best.get("published_utc", "") or "",
        source=best.get("source", "") or "",
        url=best.get("url", "") or "",
        event=_classify(text),
    )


def _sentiment_word(s: float) -> str:
    if s >= 0.45:  return "strongly positive"
    if s >= 0.15:  return "positive"
    if s <= -0.45: return "strongly negative"
    if s <= -0.15: return "negative"
    return "mixed"


_ACTION_VERBS = {
    "BUY":    "buying",
    "SELL":   "exiting",
    "REDUCE": "trimming",
    "HOLD":   "holding",
    "SKIP":   "skipping",
}


def narrate(
    action: str,
    symbol: str,
    base_reason: str,
    news_for_ticker: list[dict] | None,
) -> tuple[str, list[str]]:
    """Return (enriched_reason, extra_factor_lines).

    base_reason is the bot's terse internal reason ("underweight by 0.74%
    vs target — add", etc.). The enriched reason wraps it in human prose
    plus the most relevant headline if one was found.
    """
    extras: list[str] = []
    hit = pick_best_hit(news_for_ticker or [])

    if not hit:
        return base_reason, extras

    s_word = _sentiment_word(hit.sentiment)
    verb = _ACTION_VERBS.get(action, action.lower())

    # Build the enriched lead.
    if hit.event:
        lead = f"{verb} on {hit.event} ({s_word})"
    else:
        lead = f"{verb} on {s_word} news flow"

    enriched = f"{lead} — \"{hit.headline[:140]}\" · {base_reason}"

    extras.append(f"news_source={hit.source}")
    if hit.event:
        extras.append(f"event={hit.event}")
    extras.append(f"news_sentiment={hit.sentiment:+.2f}")
    return enriched, extras
