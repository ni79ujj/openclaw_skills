"""Mean Reversion Strategy — buy dips, sell rebounds."""
from .base import BaseStrategy, Candle, Signal, AccountState


class MeanReversionStrategy(BaseStrategy):
    """
    Logic:
    - Track the highest close over the last `lookback_candles` (default 240 = 4h)
    - If price drops `entry_drop_pct`% from that high AND no long position → BUY
    - If we're long and price recovers `take_profit_pct`% OR drops `stop_loss_pct`% → SELL

    Params:
      lookback_candles: int  (default 240)
      entry_drop_pct:  float (default 2.0)
      take_profit_pct: float (from risk config)
      stop_loss_pct:   float (from risk config)
    """

    name = "MeanReversionFox"

    def __init__(self, params: dict):
        super().__init__(params)
        self.lookback = int(params.get("lookback_candles", 240))
        self.entry_drop = float(params.get("entry_drop_pct", 2.0))
        self.tp_pct = float(params.get("take_profit_pct", 1.5))
        self.sl_pct = float(params.get("stop_loss_pct", 3.0))
        self._entry_price: float | None = None

    def on_candle(self, candle: Candle, history: list[Candle], account: AccountState) -> Signal:
        if len(history) < 10:
            return Signal(action="hold", reason="warming up")

        high = self.highest(history, self.lookback)
        price = candle.c
        has_long = self.has_open_position(account, "long")

        # Check exit first
        if has_long and self._entry_price:
            gain_pct = (price - self._entry_price) / self._entry_price * 100
            if gain_pct >= self.tp_pct:
                self._entry_price = None
                return Signal(action="sell", reason=f"take profit +{gain_pct:.2f}%")
            if gain_pct <= -self.sl_pct:
                self._entry_price = None
                return Signal(action="sell", reason=f"stop loss {gain_pct:.2f}%")

        # Entry logic
        if not has_long and high > 0:
            drop_pct = (high - price) / high * 100
            if drop_pct >= self.entry_drop:
                self._entry_price = price
                return Signal(
                    action="buy",
                    reason=f"price dropped {drop_pct:.2f}% from {self.lookback}c high",
                    stop_price=price * (1 - self.sl_pct / 100),
                    target_price=price * (1 + self.tp_pct / 100),
                )

        return Signal(action="hold")
