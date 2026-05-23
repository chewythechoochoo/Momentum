"""Theme universe — each theme bundles a small set of liquid US-listed tickers and keywords.

Keep the universe SMALL and LIQUID. Anything illiquid or speculative is rejected by risk.py.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    key: str
    name: str
    tickers: tuple[str, ...]
    keywords: tuple[str, ...]   # used for news fallback queries


THEMES: tuple[Theme, ...] = (
    Theme(
        key="ai_compute",
        name="AI & Compute",
        tickers=("NVDA", "AMD", "AVGO", "SMCI", "MSFT", "GOOGL", "META"),
        keywords=("AI", "GPU", "datacenter", "LLM", "generative AI", "inference"),
    ),
    Theme(
        key="ev_clean_transport",
        name="EV & Clean Transport",
        tickers=("TSLA", "RIVN", "GM", "F", "LCID"),
        keywords=("electric vehicle", "EV", "battery", "charging"),
    ),
    Theme(
        key="clean_energy",
        name="Clean Energy",
        tickers=("ENPH", "FSLR", "NEE", "SEDG", "RUN"),
        keywords=("solar", "renewable energy", "clean energy", "grid", "IRA tax credit"),
    ),
    Theme(
        key="oil_gas",
        name="Oil & Gas",
        tickers=("XOM", "CVX", "COP", "OXY", "SLB"),
        keywords=("crude oil", "OPEC", "refinery", "natural gas", "drilling"),
    ),
    Theme(
        key="defense",
        name="Defense & Aerospace",
        tickers=("LMT", "RTX", "NOC", "GD", "BA"),
        keywords=("defense contract", "Pentagon", "DOD", "missile", "aerospace"),
    ),
    Theme(
        key="biotech",
        name="Biotech & Pharma",
        tickers=("LLY", "PFE", "MRNA", "REGN", "VRTX"),
        keywords=("FDA approval", "clinical trial", "drug pipeline", "biotech"),
    ),
    Theme(
        key="cybersecurity",
        name="Cybersecurity",
        tickers=("CRWD", "PANW", "ZS", "FTNT", "OKTA"),
        keywords=("cybersecurity", "ransomware", "zero trust", "breach"),
    ),
    Theme(
        key="financials",
        name="Financials & Rates",
        tickers=("JPM", "BAC", "GS", "MS", "WFC"),
        keywords=("Fed", "interest rates", "bank earnings", "yield curve"),
    ),
    Theme(
        key="consumer_discretionary",
        name="Consumer Discretionary",
        tickers=("AMZN", "HD", "NKE", "MCD", "SBUX"),
        keywords=("consumer spending", "retail sales", "discretionary"),
    ),
    Theme(
        key="semiconductors_ex_ai",
        name="Semiconductors (Broad)",
        tickers=("TSM", "ASML", "AMAT", "LRCX", "MU"),
        keywords=("semiconductor", "chip", "foundry", "wafer", "memory"),
    ),
)


def get_theme(key: str) -> Theme | None:
    for t in THEMES:
        if t.key == key:
            return t
    return None


def all_tickers() -> list[str]:
    seen: dict[str, None] = {}
    for t in THEMES:
        for s in t.tickers:
            seen.setdefault(s, None)
    return list(seen.keys())
