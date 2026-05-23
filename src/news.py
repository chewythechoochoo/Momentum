"""News aggregation with a fallback chain: Alpaca News → Yahoo Finance RSS → NewsAPI."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

import feedparser
import requests

from .config import SETTINGS
from .logger import get_logger, log_event

log = get_logger(__name__)

_ALPACA_NEWS_URL = "https://data.alpaca.markets/v1beta1/news"
_NEWSAPI_URL = "https://newsapi.org/v2/everything"
_YAHOO_RSS = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={syms}&region=US&lang=en-US"


@dataclass
class NewsItem:
    headline: str
    summary: str
    source: str
    url: str
    symbols: list[str]
    published_utc: datetime


def _safe_dt(value) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return datetime.now(timezone.utc)


def fetch_alpaca_news(symbols: Iterable[str], hours_back: int = 24, limit: int = 50) -> list[NewsItem]:
    headers = {
        "Apca-Api-Key-Id": SETTINGS.alpaca_key,
        "Apca-Api-Secret-Key": SETTINGS.alpaca_secret,
    }
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours_back)
    params = {
        "symbols": ",".join(symbols),
        "start": start.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "end": end.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "limit": limit,
        "sort": "desc",
    }
    try:
        resp = requests.get(_ALPACA_NEWS_URL, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        log_event(log, "news_alpaca_failed", error=str(e))
        return []

    items: list[NewsItem] = []
    for n in resp.json().get("news", []):
        items.append(
            NewsItem(
                headline=n.get("headline", ""),
                summary=n.get("summary", ""),
                source=n.get("source", "alpaca"),
                url=n.get("url", ""),
                symbols=list(n.get("symbols", []) or []),
                published_utc=_safe_dt(n.get("created_at")),
            )
        )
    return items


def fetch_yahoo_rss(symbols: Iterable[str]) -> list[NewsItem]:
    syms = ",".join(symbols)
    if not syms:
        return []
    url = _YAHOO_RSS.format(syms=syms)
    try:
        feed = feedparser.parse(url)
    except Exception as e:  # noqa: BLE001
        log_event(log, "news_yahoo_failed", error=str(e))
        return []

    items: list[NewsItem] = []
    for entry in feed.entries[:50]:
        # Yahoo RSS doesn't always tag symbols. We assume the ticker(s) in the query
        # if the headline mentions them; otherwise tag with the full query set.
        headline = entry.get("title", "")
        tagged = [s for s in symbols if s in headline]
        items.append(
            NewsItem(
                headline=headline,
                summary=entry.get("summary", ""),
                source="yahoo_rss",
                url=entry.get("link", ""),
                symbols=tagged or list(symbols),
                published_utc=_safe_dt(entry.get("published")),
            )
        )
    return items


def fetch_newsapi(keywords: str, hours_back: int = 24, limit: int = 50) -> list[NewsItem]:
    if not SETTINGS.newsapi_key:
        return []
    params = {
        "q": keywords,
        "from": (datetime.now(timezone.utc) - timedelta(hours=hours_back)).date().isoformat(),
        "sortBy": "publishedAt",
        "language": "en",
        "pageSize": min(limit, 100),
        "apiKey": SETTINGS.newsapi_key,
    }
    try:
        resp = requests.get(_NEWSAPI_URL, params=params, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        log_event(log, "news_newsapi_failed", error=str(e))
        return []
    items: list[NewsItem] = []
    for n in resp.json().get("articles", []):
        items.append(
            NewsItem(
                headline=n.get("title", ""),
                summary=n.get("description", "") or "",
                source=(n.get("source") or {}).get("name", "newsapi"),
                url=n.get("url", ""),
                symbols=[],
                published_utc=_safe_dt(n.get("publishedAt")),
            )
        )
    return items


def fetch_news_for_symbols(symbols: list[str], keywords: str = "") -> list[NewsItem]:
    """Try Alpaca first, fall back to Yahoo RSS, then NewsAPI if configured."""
    items = fetch_alpaca_news(symbols)
    log_event(log, "news_source_used", source="alpaca", count=len(items), symbols=symbols)
    if items:
        return items

    items = fetch_yahoo_rss(symbols)
    log_event(log, "news_source_used", source="yahoo_rss", count=len(items), symbols=symbols)
    if items:
        return items

    if keywords:
        items = fetch_newsapi(keywords)
        log_event(log, "news_source_used", source="newsapi", count=len(items), symbols=symbols)
    return items
