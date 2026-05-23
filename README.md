# Momentum — paper-trading news + momentum theme-rotation agent

A conservative, audit-friendly research bot. It runs every 15 minutes on GitHub
Actions, scores ~10 equity themes from news + momentum + volume + policy signals,
rotates capital across themes via the Alpaca **paper** trading API, and
publishes a read-only dashboard to GitHub Pages.

> **PAPER TRADING ONLY.** The code refuses to start against any live-money
> endpoint or key. There is no real-money mode, no margin, no shorting, no
> options, and no leverage.

---

## What it does, in one screen

1. **Pre-flight safety.** Refuses to start unless `ALPACA_PAPER=true`, paper-style
   API keys are present, and the previous cycle was ≥ `MIN_RUN_INTERVAL_MINUTES` ago.
2. **Scores 10 themes** (AI/Compute, EV, Clean Energy, Oil & Gas, Defense, Biotech,
   Cyber, Financials, Consumer Discretionary, Semiconductors) using:
   `theme_score = 0.40·momentum + 0.30·sentiment + 0.20·volume + 0.10·policy_catalyst − vol_penalty`
3. **Allocates** per the score bands below, scaled by confidence.
4. **Builds buy / sell / reduce / hold / skip decisions** vs. current positions,
   each with a human-readable reason and the contributing factors.
5. **Executes** notional market orders during market hours only, with a 5–8%
   stop-loss attached to new positions.
6. **Publishes** `dashboard/data.json` and the static HTML dashboard via GitHub Pages.

### Score → target weight bands

| Score   | Band              | Target weight per theme |
| ------- | ----------------- | ----------------------- |
| 70–100  | `strong_buy`      | 15–20%                  |
| 55–69   | `buy`             | 10–15%                  |
| 40–54   | `starter`         |  5–10%                  |
| 35–39   | `hold_small`      |  2–5%                   |
| < 35    | `exit_or_avoid`   |  0%                     |

Confidence (news count + valid-feature share) scales the final weight: a
high-score theme with thin data lands in the lower half of its band.

### Risk rules (hard)

- ≤ 20% per theme, ≤ 7% per ticker, ≥ 0.5% min position size
- ≤ 2 *new* buys per cycle (existing positions can scale up freely within caps)
- No tickers under \$5 or with < 1M average daily volume
- 5–8% stop-loss (tightened on high-vol names)
- Theme score < 35 → halve position; < 25 → fully exit
- ≥ 5% cash buffer always held
- Halt all new buys if portfolio drawdown > 15% from high-water mark

---

## Repository layout

```
.
├── .github/workflows/trade.yml   # 15-min cron + Pages deploy
├── src/
│   ├── main.py                   # one cycle (entry point)
│   ├── config.py                 # weights, risk limits, score bands
│   ├── safety.py                 # paper-only guards, min-interval, key prefix check
│   ├── alpaca_client.py          # paper-trading wrapper around alpaca-py
│   ├── market_data.py            # price/volume/vol/RSI features from daily bars
│   ├── news.py                   # Alpaca News → Yahoo RSS → NewsAPI fallback
│   ├── sentiment.py              # keyword sentiment + policy-catalyst detector
│   ├── themes.py                 # ~10 themes, each with liquid tickers + keywords
│   ├── scoring.py                # theme_score formula + confidence
│   ├── risk.py                   # liquidity & cap checks, stop-loss math
│   ├── allocator.py              # score band → theme weight → per-ticker split
│   ├── decisions.py              # diff targets vs positions → BUY/SELL/HOLD/SKIP
│   ├── executor.py               # apply decisions (paper market orders)
│   ├── reporter.py               # build dashboard/data.json
│   ├── state.py                  # persisted cycle state (data/state.json)
│   └── logger.py                 # JSON stdout logger; secrets redacted at call sites
├── dashboard/
│   ├── index.html  styles.css  app.js   # static, vanilla
│   └── data.json                # generated each cycle; committed for Pages
├── data/                        # state.json (committed by the workflow)
├── tests/                       # scoring / risk / safety unit tests
├── requirements.txt
├── .env.example
└── README.md
```

---

## Setup

### 1. Get paper-only Alpaca keys

Sign up at <https://app.alpaca.markets/paper/dashboard/overview>. Generate a
new key pair *from the paper dashboard*. Paper keys are prefixed `PK…`. The bot
**rejects** any key prefixed `AK…` (live keys).

### 2. Configure GitHub Secrets

Add these under **Settings → Secrets and variables → Actions → Secrets**:

| Name                       | Value                                       |
| -------------------------- | ------------------------------------------- |
| `ALPACA_API_KEY_ID`        | Paper key ID, starts with `PK`              |
| `ALPACA_API_SECRET_KEY`    | Paper secret                                |
| `NEWSAPI_KEY` *(optional)* | newsapi.org free-tier key (tertiary fallback) |

> Never commit `.env`. The `.gitignore` blocks it; `safety.py` redacts keys in logs.

### 3. Enable GitHub Pages

**Settings → Pages → Build and deployment → Source: "GitHub Actions"**. The
workflow's `deploy-pages` job will publish `dashboard/` to your Pages site
after each cycle.

### 4. (Optional) Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in paper keys
python -m src.main     # runs one cycle; honors MIN_RUN_INTERVAL_MINUTES
pytest                 # run unit tests
```

The very first local run may abort if `data/state.json` records a recent
successful run — that's the min-interval guardrail. Delete `data/state.json`
to reset.

---

## How the cycle works

```
GitHub Actions cron (*/15 * * * *)
    │
    ▼
src/main.run_cycle()
    │
    ├── safety.run_preflight()              # paper-only + key check
    ├── safety.assert_min_interval()        # ≥ 14 min since last success
    ├── AlpacaPaperClient()                 # market open? account? positions?
    ├── compute_features(all_tickers)       # daily bars → returns, vol, RSI
    │
    ├── for theme in THEMES:
    │       news = fetch_news_for_symbols(theme.tickers)  # Alpaca → Yahoo → NewsAPI
    │       sentiment = sentiment.analyze(headlines+summaries)
    │       score = scoring.score_theme(theme, features, sentiment)
    │
    ├── allocator.build_targets(scores)     # score → theme weight → top tickers
    ├── decisions.build_decisions(...)      # diff vs positions, reasons + factors
    ├── if market_open: executor.apply_decisions(...)
    │   else: dry-run (decisions still surfaced on dashboard)
    │
    ├── reporter.write_dashboard(payload)   # dashboard/data.json
    └── state.save_state(...)               # last_success, cycle_count, decision log
```

The workflow then commits `dashboard/data.json` + `data/state.json` and
publishes the dashboard via the `deploy-pages` job.

---

## Sample `dashboard/data.json` schema

```jsonc
{
  "schema_version": 1,
  "generated_at_utc": "2026-05-22T20:00:00",
  "mode": "PAPER",                    // always
  "endpoint": "alpaca-paper",         // always
  "cycle_count": 132,
  "last_success_utc": "2026-05-22T19:45:00",
  "market_open": true,
  "config": {
    "weights": {"momentum": 0.4, "sentiment": 0.3, "volume": 0.2, "policy": 0.1},
    "risk": { /* caps, stop-loss range, score thresholds, cash buffer */ },
    "min_run_interval_minutes": 14
  },
  "account": {
    "equity": 100000.0, "cash": 64500.0,
    "buying_power": 64500.0, "portfolio_value": 100000.0
  },
  "positions": [
    {
      "symbol": "NVDA", "qty": 12.5, "avg_entry_price": 480.00,
      "current_price": 501.20, "market_value": 6265.00,
      "unrealized_pl": 265.00, "unrealized_plpc": 0.0440, "weight": 0.0626
    }
  ],
  "themes": [
    {
      "key": "ai_compute", "name": "AI & Compute",
      "score": 72.4, "raw_score": 78.4, "band": "strong_buy",
      "weight": 0.18, "confidence": 0.92,
      "components": {
        "momentum": 82.1, "sentiment": 71.0, "volume": 76.5,
        "policy": 60.0, "volatility_penalty": 6.0
      }
    }
  ],
  "decisions": [
    {
      "symbol": "NVDA", "action": "BUY",
      "target_weight": 0.06, "current_weight": 0.0,
      "notional_delta": 6000.0,
      "reason": "new position — theme 'AI & Compute' score 72.4 (strong_buy)",
      "factors": ["ret_5d=4.20%", "rel_vol_5d=1.35", "vol_ann=42.10%"],
      "theme_key": "ai_compute"
    }
  ],
  "executions": [ { /* same as decisions, plus executed, order, optional error/note */ } ],
  "notes": [ "Market is closed — decisions are advisory; no orders placed." ]
}
```

The `data.json` is the only structured artifact the dashboard reads — it never
contains keys, account IDs, or anything other than aggregate state.

---

## Safety notes

- **No live trading.** `safety.assert_paper_only()` rejects any non-`true` value
  for `ALPACA_PAPER`, any URL containing `api.alpaca.markets`/`live`, and any
  key prefixed `AK…`. The workflow re-checks the same invariants before invoking
  the bot.
- **15-minute floor.** Even if a workflow misfires, the bot self-rejects runs
  closer than `MIN_RUN_INTERVAL_MINUTES` (default 14) since the last success.
  `concurrency.group` on the workflow also prevents overlapping runs.
- **No leverage, no shorting, no options, no margin, no penny stocks, no
  illiquid tickers.** All enforced in `risk.py`.
- **Transparent decisions.** Every cycle writes a full decision list (incl.
  HOLD/SKIP with reasons) to the dashboard. The last 200 decisions are also
  persisted in `data/state.json` for audit.
- **Secrets stay out of the repo and the frontend.** `dashboard/data.json` is
  generated by `reporter.py`, which never touches credentials.

---

## License

MIT. For research/education only — not financial advice.
