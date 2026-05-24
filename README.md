# Momentum

A conservative paper-trading research bot. Every 15 minutes, it scores ~10
equity themes from price, volume, news, and policy signals, then rotates a
paper-portfolio across the strongest themes via Alpaca's **paper** trading
API. Output is a static read-only dashboard published to GitHub Pages.

> **Paper trading only.** The code rejects any live-money endpoint, key, or
> URL at startup. No real-money mode, no margin, no shorting, no options,
> no leverage.

**Live dashboard:** <https://chewythechoochoo.github.io/Momentum/>

---

## What the agent does, per cycle

1. Pulls account state from Alpaca's paper endpoint.
2. Fetches 60 days of daily bars and 24 hours of headlines for ~50 liquid US
   tickers across 10 themes.
3. Scores every theme (formula below).
4. Maps each score to a target weight via the bands below.
5. Diffs targets vs. current positions and emits BUY / SELL / REDUCE / HOLD /
   SKIP decisions, each with a human-readable reason + contributing factors.
6. Places notional market orders during US market hours; attaches a 5–8 %
   stop-loss to every new position.
7. Writes `dashboard/data.json` and `data/state.json` and pushes them back —
   the dashboard reads only that JSON.

---

## Scoring formula

Each theme gets a score on **0 – 100**:

```
theme_score = 0.40 · momentum
            + 0.30 · sentiment
            + 0.20 · volume
            + 0.10 · policy_catalyst
            − volatility_penalty            (0 – 30)
```

Every sub-score is normalised to 0 – 100 before weighting:

| Component         | What it measures                                                                 |
| ----------------- | -------------------------------------------------------------------------------- |
| `momentum`        | Blend of 1-day / 5-day / 20-day returns across the theme's tickers               |
| `sentiment`       | `(positive − negative keyword hits) / total`, mapped to 0–100 with neutral at 50 |
| `volume`          | 5-day average volume / 20-day average volume, log-shaped to 0–100                |
| `policy_catalyst` | Count of policy keywords (Fed, EPA, FDA, executive order, tariff, …) in 24 h    |
| `volatility_penalty` | `max(0, annualised_vol − 0.30) × 35`, capped at 30 points                      |

A confidence score (`0 – 1`) accompanies every theme:

```
confidence = 0.6 · valid_feature_share + 0.4 · min(1, news_count / 8)
```

## Ranking → target weight

| Score      | Band              | Target weight per theme |
| ---------- | ----------------- | ----------------------- |
| 70 – 100   | `strong_buy`      | 15 – 20 %               |
| 55 – 69    | `buy`             | 10 – 15 %               |
| 40 – 54    | `starter`         |  5 – 10 %               |
| 35 – 39    | `hold_small`      |  2 – 5 %                |
| < 35       | `exit_or_avoid`   |  0 %                    |

```
final_theme_weight = band_target_weight × (0.5 + 0.5 · confidence)
```

Inside a theme, the **top 3 tickers** share its weight in proportion to a
ticker-level contribution score:

```
contribution(ticker) = 0.40 · ticker_momentum
                     + 0.30 · theme_sentiment
                     + 0.20 · ticker_rel_volume
                     + 0.10 · theme_policy
                     − ticker_volatility_penalty
```

**Hard risk caps:** ≤ 20 % per theme · ≤ 7 % per ticker · ≤ 2 new buys per
cycle · 5 – 8 % stop-loss · reduce at theme score < 35, exit at < 25 ·
≥ 5 % cash buffer · halt new buys if portfolio drawdown > 15 % from
high-water mark.

---

## Where the data comes from

| Stream | Source(s) | Notes |
| --- | --- | --- |
| Account, orders, market clock | [Alpaca Paper Trading API](https://docs.alpaca.markets/docs/about-trading-api) | `paper-api.alpaca.markets` — no live endpoints accepted |
| Daily bars (60 d) | [Alpaca Market Data v2](https://docs.alpaca.markets/docs/about-market-data-api) | Powers momentum, volume, RSI, volatility |
| Per-theme news (24 h) | [Alpaca News API](https://docs.alpaca.markets/docs/about-news-api) → [Yahoo Finance RSS](https://finance.yahoo.com/) → [NewsAPI.org](https://newsapi.org/) | Fallback chain; stops at the first source returning ≥ 1 item |
| Breaking-news ticker | Yahoo Finance, MarketWatch, BBC Business, BBC World, NPR Business — public RSS feeds | Aggregated and deduped server-side; sentiment scored locally |
| Sentiment + policy detection | `src/sentiment.py` (keyword matching) | No external API — fully auditable |

All fetching runs inside the GitHub Actions runner. The published dashboard
reads only `dashboard/data.json` and contains no keys, account IDs, or other
secrets.

---

## License

MIT. For research and education only — not financial advice.
