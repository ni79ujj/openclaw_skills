"""
Momentum Strategy — ClawSwap Agent Template
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Go long when price breaks above recent high.
Trailing stop loss to lock in profits.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MomentumConfig:
    ticker: str = "ETH"
    leverage: float = 3.0
    position_size_pct: float = 0.2
    breakout_lookback: int = 96         # 24h high (15min × 96)
    breakout_confirm_pct: float = 0.3   # Price must exceed high by 0.3%
    take_profit_pct: float = 5.0
    trailing_stop_pct: float = 2.0      # Trailing stop 2% below peak
    max_open_positions: int = 1


@dataclass
class MomentumState:
    in_position: bool = False
    entry_price: float = 0.0
    peak_price: float = 0.0
    position_id: Optional[str] = None
    candle_buffer: list = field(default_factory=list)


class MomentumStrategy:
    def __init__(self, cfg: MomentumConfig | None = None):
        self.cfg = cfg or MomentumConfig()
        self.state = MomentumState()

    def on_candle(self, candle: dict) -> None:
        self.state.candle_buffer.append(candle["close"])
        if len(self.state.candle_buffer) > self.cfg.breakout_lookback * 2:
            self.state.candle_buffer.pop(0)

    def get_signal(self) -> Optional[str]:
        if self.state.in_position:
            return None
        buf = self.state.candle_buffer
        if len(buf) < self.cfg.breakout_lookback:
            return None
        recent_high = max(buf[-self.cfg.breakout_lookback:-1])  # exclude current
        current = buf[-1]
        breakout_level = recent_high * (1 + self.cfg.breakout_confirm_pct / 100)
        if current >= breakout_level:
            return "buy"
        return None

    def get_exit_signal(self, current_price: float) -> Optional[str]:
        if not self.state.in_position:
            return None
        # Update peak
        if current_price > self.state.peak_price:
            self.state.peak_price = current_price
        # Trailing stop
        trail_stop = self.state.peak_price * (1 - self.cfg.trailing_stop_pct / 100)
        if current_price <= trail_stop:
            return "trailing_stop"
        # Take profit
        pnl_pct = (current_price - self.state.entry_price) / self.state.entry_price * 100
        if pnl_pct >= self.cfg.take_profit_pct:
            return "take_profit"
        return None

    def on_fill(self, side: str, price: float, position_id: str) -> None:
        if side == "buy":
            self.state.in_position = True
            self.state.entry_price = price
            self.state.peak_price = price
            self.state.position_id = position_id
        elif side == "sell":
            self.state.in_position = False
            self.state.entry_price = 0.0
            self.state.peak_price = 0.0
            self.state.position_id = None
