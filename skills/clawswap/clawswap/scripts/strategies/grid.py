"""Grid Trading Strategy — buy/sell at fixed price intervals."""
from .base import BaseStrategy, Candle, Signal, AccountState


class GridStrategy(BaseStrategy):
    """
    Logic:
    - Center grid at startup price
    - Place N buy levels below center, N sell levels above
    - When price crosses a grid level → trigger order at that level
    - Re-centers every `recenter_candles` candles if price drifts far

    Params:
      grid_levels:    int   (default 5)    — levels each side
      grid_spacing_pct: float (default 1.0) — % spacing between levels
      recenter_candles: int (default 1440) — recenter after N candles
    """

    name = "GridSpider"

    def __init__(self, params: dict):
        super().__init__(params)
        self.levels = int(params.get("grid_levels", 5))
        self.spacing = float(params.get("grid_spacing_pct", 1.0))
        self.recenter_after = int(params.get("recenter_candles", 1440))
        self._center: float | None = None
        self._grid: list[float] = []
        self._last_price: float | None = None
        self._candle_count = 0

    def _build_grid(self, center: float) -> list[float]:
        """Build grid levels around center price."""
        grid = []
        for i in range(-self.levels, self.levels + 1):
            if i != 0:
                grid.append(center * (1 + i * self.spacing / 100))
        return sorted(grid)

    def on_start(self, config: dict) -> None:
        self._center = None  # will set on first candle

    def on_candle(self, candle: Candle, history: list[Candle], account: AccountState) -> Signal:
        price = candle.c
        self._candle_count += 1

        # Initialize grid on first candle
        if self._center is None:
            self._center = price
            self._grid = self._build_grid(price)
            self._last_price = price
            return Signal(action="hold", reason="grid initialized")

        # Periodic recenter if price drifted > 3x spacing from center
        drift_pct = abs(price - self._center) / self._center * 100
        if self._candle_count % self.recenter_after == 0 and drift_pct > self.spacing * 3:
            self._center = price
            self._grid = self._build_grid(price)
            return Signal(action="hold", reason=f"grid recentered @ ${price:.2f}")

        # Check if price crossed a grid level
        if self._last_price is None:
            self._last_price = price
            return Signal(action="hold")

        # Find crossed levels between last and current price
        signal = Signal(action="hold")
        for level in self._grid:
            if self._last_price < level <= price:
                # Price moved up through this level → sell
                if level > self._center and not self.has_open_position(account, "short"):
                    signal = Signal(action="sell", reason=f"grid sell @ ${level:.2f}", size_pct=100 / self.levels)
                    break
            elif self._last_price > level >= price:
                # Price moved down through this level → buy
                if level < self._center and not self.has_open_position(account, "long"):
                    signal = Signal(action="buy", reason=f"grid buy @ ${level:.2f}", size_pct=100 / self.levels)
                    break

        self._last_price = price
        return signal
