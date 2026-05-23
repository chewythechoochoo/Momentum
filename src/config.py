"""Central configuration: env loading, risk constants, score-band → allocation map."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Final

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class RiskLimits:
    max_theme_weight: float = 0.20            # 20% per theme cap
    max_ticker_weight: float = 0.07           # 7% per ticker cap
    min_ticker_weight: float = 0.005          # ignore positions below 0.5%
    max_new_buys_per_cycle: int = 2
    stop_loss_pct: float = 0.07               # 7% default trailing stop
    stop_loss_pct_min: float = 0.05           # tighter on volatile names
    stop_loss_pct_max: float = 0.08
    min_price: float = 5.00                   # no penny stocks
    min_avg_daily_volume: float = 1_000_000   # liquidity floor
    reduce_below_score: float = 35.0
    exit_below_score: float = 25.0
    cash_buffer_pct: float = 0.05             # always keep ≥5% cash
    max_portfolio_drawdown_pct: float = 0.15  # halt new buys if portfolio down >15%


@dataclass(frozen=True)
class ScoringWeights:
    momentum: float = 0.40
    sentiment: float = 0.30
    volume: float = 0.20
    policy: float = 0.10


@dataclass(frozen=True)
class ScoreBand:
    """A score band maps to a target weight RANGE per qualifying theme."""

    min_score: float
    max_score: float
    target_min: float
    target_max: float
    label: str


# Score → allocation bands. Bands are inclusive of min, exclusive of max
# except the top band which is inclusive of 100.
SCORE_BANDS: Final[tuple[ScoreBand, ...]] = (
    ScoreBand(70.0, 100.01, 0.15, 0.20, "strong_buy"),
    ScoreBand(55.0, 70.0, 0.10, 0.15, "buy"),
    ScoreBand(40.0, 55.0, 0.05, 0.10, "starter"),
    ScoreBand(35.0, 40.0, 0.02, 0.05, "hold_small"),
    ScoreBand(0.0, 35.0, 0.00, 0.00, "exit_or_avoid"),
)


@dataclass(frozen=True)
class Settings:
    # Alpaca — paper only
    alpaca_key: str = os.getenv("ALPACA_API_KEY_ID", "")
    alpaca_secret: str = os.getenv("ALPACA_API_SECRET_KEY", "")
    alpaca_paper: bool = os.getenv("ALPACA_PAPER", "true").lower() == "true"
    alpaca_base_url_override: str = os.getenv("ALPACA_BASE_URL", "").strip()

    newsapi_key: str = os.getenv("NEWSAPI_KEY", "")

    # Operational guardrails
    min_run_interval_minutes: int = int(os.getenv("MIN_RUN_INTERVAL_MINUTES", "14"))
    trading_enabled: bool = os.getenv("TRADING_ENABLED", "true").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()

    # Paths
    repo_root: str = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    state_path: str = field(init=False)
    dashboard_data_path: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "state_path", os.path.join(self.repo_root, "data", "state.json"))
        object.__setattr__(
            self,
            "dashboard_data_path",
            os.path.join(self.repo_root, "dashboard", "data.json"),
        )


SETTINGS = Settings()
RISK = RiskLimits()
WEIGHTS = ScoringWeights()

# Alpaca paper endpoint — hardcoded so it cannot be overridden by env alone
# without also tripping the safety check in safety.py.
ALPACA_PAPER_ENDPOINT: Final[str] = "https://paper-api.alpaca.markets"
ALPACA_DATA_ENDPOINT: Final[str] = "https://data.alpaca.markets"
