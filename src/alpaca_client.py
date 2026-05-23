"""Thin wrapper around alpaca-py. All instances are paper-only by construction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, OrderStatus, TimeInForce
from alpaca.trading.requests import (
    GetOrdersRequest,
    LimitOrderRequest,
    MarketOrderRequest,
)

from .config import SETTINGS
from .logger import get_logger, log_event
from .safety import run_preflight

log = get_logger(__name__)


@dataclass(frozen=True)
class Position:
    symbol: str
    qty: float
    avg_entry_price: float
    market_value: float
    unrealized_pl: float
    unrealized_plpc: float
    current_price: float


@dataclass(frozen=True)
class Account:
    equity: float
    cash: float
    buying_power: float
    portfolio_value: float
    daytrade_count: int
    pattern_day_trader: bool


class AlpacaPaperClient:
    """Paper-trading client. Safety preflight runs in __init__ and on every order."""

    def __init__(self) -> None:
        self.paper_endpoint = run_preflight()
        # alpaca-py's TradingClient with paper=True hits the paper endpoint regardless
        # of any url override; we still validate above.
        self.trading = TradingClient(
            api_key=SETTINGS.alpaca_key,
            secret_key=SETTINGS.alpaca_secret,
            paper=True,
        )
        self.data = StockHistoricalDataClient(
            api_key=SETTINGS.alpaca_key,
            secret_key=SETTINGS.alpaca_secret,
        )
        log_event(log, "alpaca_client_init", endpoint=self.paper_endpoint, paper=True)

    # ---- Account & positions ----

    def get_account(self) -> Account:
        a = self.trading.get_account()
        return Account(
            equity=float(a.equity),
            cash=float(a.cash),
            buying_power=float(a.buying_power),
            portfolio_value=float(a.portfolio_value),
            daytrade_count=int(getattr(a, "daytrade_count", 0) or 0),
            pattern_day_trader=bool(getattr(a, "pattern_day_trader", False)),
        )

    def get_positions(self) -> list[Position]:
        out: list[Position] = []
        for p in self.trading.get_all_positions():
            out.append(
                Position(
                    symbol=p.symbol,
                    qty=float(p.qty),
                    avg_entry_price=float(p.avg_entry_price),
                    market_value=float(p.market_value),
                    unrealized_pl=float(p.unrealized_pl),
                    unrealized_plpc=float(p.unrealized_plpc),
                    current_price=float(p.current_price),
                )
            )
        return out

    # ---- Market data ----

    def get_bars(
        self,
        symbols: Iterable[str],
        start: datetime,
        end: datetime,
        timeframe: TimeFrame = TimeFrame.Day,
    ):
        req = StockBarsRequest(
            symbol_or_symbols=list(symbols),
            timeframe=timeframe,
            start=start,
            end=end,
        )
        return self.data.get_stock_bars(req).df

    def get_latest_quotes(self, symbols: Iterable[str]):
        req = StockLatestQuoteRequest(symbol_or_symbols=list(symbols))
        return self.data.get_stock_latest_quote(req)

    # ---- Orders ----

    def submit_market_order(
        self, symbol: str, notional: float, side: OrderSide
    ) -> dict | None:
        """Notional-based market order — fractional-share friendly. Returns a summary dict."""
        if not SETTINGS.trading_enabled:
            log_event(
                log, "order_skipped_dry_run", symbol=symbol, notional=notional, side=str(side)
            )
            return None
        req = MarketOrderRequest(
            symbol=symbol,
            notional=round(notional, 2),
            side=side,
            time_in_force=TimeInForce.DAY,
        )
        order = self.trading.submit_order(order_data=req)
        log_event(
            log,
            "order_submitted",
            symbol=symbol,
            notional=notional,
            side=str(side),
            id=str(order.id),
            status=str(order.status),
        )
        return {
            "id": str(order.id),
            "symbol": symbol,
            "notional": notional,
            "side": str(side),
            "status": str(order.status),
            "submitted_at": str(order.submitted_at),
        }

    def submit_stop_loss(self, symbol: str, qty: float, stop_price: float) -> dict | None:
        if not SETTINGS.trading_enabled:
            return None
        req = LimitOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.SELL,
            limit_price=round(stop_price, 2),
            time_in_force=TimeInForce.GTC,
        )
        order = self.trading.submit_order(order_data=req)
        return {"id": str(order.id), "symbol": symbol, "qty": qty, "stop": stop_price}

    def list_open_orders(self) -> list[dict]:
        req = GetOrdersRequest(status=OrderStatus.OPEN, limit=200)
        orders = self.trading.get_orders(filter=req)
        return [
            {
                "id": str(o.id),
                "symbol": o.symbol,
                "side": str(o.side),
                "qty": float(o.qty or 0),
                "notional": float(o.notional or 0),
                "status": str(o.status),
            }
            for o in orders
        ]

    def is_market_open(self) -> bool:
        clock = self.trading.get_clock()
        return bool(clock.is_open)
