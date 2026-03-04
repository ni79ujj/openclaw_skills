"""
Mean Reversion Strategy — ClawSwap Agent Template
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Buy when price drops X% from recent high.
Take profit at Y%, stop loss at Z%.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import time


@dataclass
class MeanReversionConfig:
    ticker: str = "BTC"
    leverage: float = 2.0
    position_size_pct: float = 0.2      # 20% of equity per trade
    lookback_candles: int = 96          # 4h high lookback (15min candles × 96 = 24h)
    entry_drop_pct: float = 2.0         # Buy when price drops 2% from high
    take_profit_pct: float = 1.5        # Take profit at +1.5%
    stop_loss_pct: float = 3.0          # Stop loss at -3%
    max_open_positions: int = 1         # Max concurrent positions


@dataclass
class StrategyState:
    in_position: bool = False
    entry_price: float = 0.0
    position_id: Optional[str] = None
    recent_high: float = 0.0
    candle_buffer: list = field(default_factory=list)


def compute_signal(prices: list[float], cfg: MeanReversionConfig) -> Optional[str]:
    """
    Returns 'buy', 'sell', or None.
    prices: list of recent close prices (newest last)
    """
    if len(prices) < cfg.lookback_candles:
        return None

    recent = prices[-cfg.lookback_candles:]
    high = max(recent)
    current = prices[-1]
    drop_pct = (high - current) / high * 100

    if drop_pct >= cfg.entry_drop_pct:
        return "buy"
    return None


def should_exit(entry_price: float, current_price: float, cfg: MeanReversionConfig) -> Optional[str]:
    """Returns 'take_profit', 'stop_loss', or None."""
    pnl_pct = (current_price - entry_price) / entry_price * 100
    if pnl_pct >= cfg.take_profit_pct:
        return "take_profit"
    if pnl_pct <= -cfg.stop_loss_pct:
        return "stop_loss"
    return None


class MeanReversionStrategy:
    """
    Stateful wrapper for use with the ClawSwap agent runner.
    Implement run_cycle() — called every 30s by the agent.
    """

    def __init__(self, cfg: MeanReversionConfig | None = None):
        self.cfg = cfg or MeanReversionConfig()
        self.state = StrategyState()

    def on_candle(self, candle: dict) -> None:
        """Feed a new candle. candle = {open, high, low, close, volume, timestamp}"""
        self.state.candle_buffer.append(candle["close"])
        if len(self.state.candle_buffer) > self.cfg.lookback_candles * 2:
            self.state.candle_buffer.pop(0)

    def get_signal(self) -> Optional[str]:
        """Return entry signal."""
        if self.state.in_position:
            return None
        return compute_signal(self.state.candle_buffer, self.cfg)

    def get_exit_signal(self, current_price: float) -> Optional[str]:
        """Return exit reason if we should close."""
        if not self.state.in_position:
            return None
        return should_exit(self.state.entry_price, current_price, self.cfg)

    def on_fill(self, side: str, price: float, position_id: str) -> None:
        if side == "buy":
            self.state.in_position = True
            self.state.entry_price = price
            self.state.position_id = position_id
        elif side == "sell":
            self.state.in_position = False
            self.state.entry_price = 0.0
            self.state.position_id = None
