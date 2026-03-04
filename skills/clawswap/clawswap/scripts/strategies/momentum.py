"""Momentum / Breakout Strategy — follow the trend with trailing stop."""
from .base import BaseStrategy, Candle, Signal, AccountState


class MomentumStrategy(BaseStrategy):
    """
    Logic:
    - Go long when price breaks above the highest high of last `breakout_lookback` candles
    - Trail stop at `trailing_stop_pct`% below running high
    - Close if trailing stop hit

    Params:
      breakout_lookback: int   (default 1440 = 24h)
      trailing_stop_pct: float (default 2.0)
    """

    name = "MomentumWolf"

    def __init__(self, params: dict):
        super().__init__(params)
        self.lookback = int(params.get("breakout_lookback", 1440))
        self.trail_pct = float(params.get("trailing_stop_pct", 2.0))
        self._trailing_high: float | None = None
        self._in_position = False

    def on_candle(self, candle: Candle, history: list[Candle], account: AccountState) -> Signal:
        if len(history) < max(self.lookback, 10):
            return Signal(action="hold", reason="warming up")

        price = candle.c
        has_long = self.has_open_position(account, "long")

        # Sync position state
        if not has_long:
            self._in_position = False
            self._trailing_high = None

        # If in position: update trailing high, check stop
        if has_long and self._in_position:
            if self._trailing_high is None or price > self._trailing_high:
                self._trailing_high = price
            stop = self._trailing_high * (1 - self.trail_pct / 100)
            if price <= stop:
                self._in_position = False
                self._trailing_high = None
                return Signal(action="sell", reason=f"trailing stop hit @ ${stop:.2f}")
            return Signal(action="hold")

        # Entry: breakout above prior N-candle high (exclude current)
        prev_high = self.highest(history[:-1], self.lookback)
        if price > prev_high and not has_long:
            self._in_position = True
            self._trailing_high = price
            return Signal(
                action="buy",
                reason=f"breakout above {self.lookback}c high ${prev_high:.2f}",
            )

        return Signal(action="hold")
