"""Base strategy class for ClawSwap agents."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass
class Candle:
    ts: int       # unix ms
    o: float      # open
    h: float      # high
    l: float      # low
    c: float      # close
    v: float      # volume


@dataclass
class Signal:
    action: Literal["buy", "sell", "hold"]
    size_pct: float = 100.0          # % of available margin
    reason: str = ""
    target_price: Optional[float] = None
    stop_price: Optional[float] = None


@dataclass
class Position:
    ticker: str
    side: Literal["long", "short"]
    size: float
    entry_price: float
    leverage: float
    unrealized_pnl: float = 0.0


@dataclass
class AccountState:
    equity: float
    available_margin: float
    positions: list[Position] = field(default_factory=list)


class BaseStrategy:
    """
    Extend this class to implement a custom strategy.

    Required:
        name: str — display name
        on_candle(candle, history, account) -> Signal

    Optional:
        on_start(config)         — called once at startup
        on_trade_filled(trade)   — called after each trade execution
    """

    name: str = "CustomStrategy"

    def __init__(self, params: dict):
        self.params = params

    def on_start(self, config: dict) -> None:
        """Called once when the agent starts. Override for initialization."""
        pass

    def on_candle(
        self,
        candle: Candle,
        history: list[Candle],
        account: AccountState,
    ) -> Signal:
        """
        Called on every new 1-minute candle.
        Return a Signal with action="buy"|"sell"|"hold".
        """
        raise NotImplementedError

    def on_trade_filled(self, trade: dict) -> None:
        """Called after a trade is executed. Override for logging."""
        pass

    # ── Utility helpers ────────────────────────────────────────────────────

    @staticmethod
    def sma(candles: list[Candle], period: int) -> float:
        """Simple moving average of close prices."""
        if len(candles) < period:
            return candles[-1].c if candles else 0.0
        return sum(c.c for c in candles[-period:]) / period

    @staticmethod
    def ema(candles: list[Candle], period: int) -> float:
        """Exponential moving average of close prices."""
        if not candles:
            return 0.0
        k = 2 / (period + 1)
        ema_val = candles[0].c
        for c in candles[1:]:
            ema_val = c.c * k + ema_val * (1 - k)
        return ema_val

    @staticmethod
    def highest(candles: list[Candle], period: int) -> float:
        """Highest high over last N candles."""
        subset = candles[-period:] if len(candles) >= period else candles
        return max(c.h for c in subset) if subset else 0.0

    @staticmethod
    def lowest(candles: list[Candle], period: int) -> float:
        """Lowest low over last N candles."""
        subset = candles[-period:] if len(candles) >= period else candles
        return min(c.l for c in subset) if subset else 0.0

    def has_open_position(self, account: AccountState, side: str = "") -> bool:
        """Check if we have an open position (optionally filter by side)."""
        for pos in account.positions:
            if not side or pos.side == side:
                return True
        return False
