#!/usr/bin/env python3
"""
ClawSwap — Local Backtest Engine
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Runs strategy backtests on locally cached Binance candle data.
No internet required at runtime (data must be pre-downloaded).

Usage:
    python backtest.py --strategy mean_reversion --ticker BTC --days 30
    python backtest.py --strategy momentum --ticker ETH --days 60
    python backtest.py --strategy grid --ticker SOL --days 90
    python backtest.py --strategy mean_reversion --config '{"entry_drop_pct": 1.5}'
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import pandas as pd
except ImportError:
    print("Missing: pip install pandas")
    sys.exit(1)

# Strategy imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from strategies import STRATEGY_MAP


# ── Types ──────────────────────────────────────────────────────────────────

@dataclass
class BacktestResult:
    strategy: str
    ticker: str
    days: int
    initial_equity: float
    final_equity: float
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate: float
    total_trades: int
    profit_factor: float
    avg_trade_pnl: float
    pnl_curve: list[float]
    elapsed_ms: int


# ── Engine ─────────────────────────────────────────────────────────────────

def load_candles(ticker: str, days: int, data_dir: Path) -> pd.DataFrame:
    symbol = ticker.upper() + "USDT" if not ticker.upper().endswith("USDT") else ticker.upper()
    # Try merged file first
    merged = data_dir / f"{symbol}-15m-merged-{days}d.csv"
    if merged.exists():
        df = pd.read_csv(merged, parse_dates=["open_time"])
        return df.tail(days * 96)  # 96 candles/day for 15m

    # Fall back to any available merged
    candidates = sorted(data_dir.glob(f"{symbol}-15m-merged-*.csv"))
    if candidates:
        df = pd.read_csv(candidates[-1], parse_dates=["open_time"])
        return df.tail(days * 96)

    raise FileNotFoundError(
        f"No data for {symbol}. Run: python scripts/download_data.py --tickers {ticker} --days {days}"
    )


def run_backtest(
    strategy_name: str,
    ticker: str,
    days: int,
    initial_equity: float = 10_000.0,
    config_overrides: dict | None = None,
    data_dir: Path | None = None,
) -> BacktestResult:
    if data_dir is None:
        data_dir = Path(__file__).parent.parent / "data" / "candles"

    t0 = time.time()

    # Load data
    df = load_candles(ticker, days, data_dir)
    if len(df) < 50:
        raise ValueError(f"Not enough candle data: {len(df)} candles")

    # Init strategy
    if strategy_name not in STRATEGY_MAP:
        raise ValueError(f"Unknown strategy: {strategy_name}. Available: {list(STRATEGY_MAP.keys())}")

    StratClass, CfgClass = STRATEGY_MAP[strategy_name]
    cfg_kwargs = {"ticker": ticker}
    if config_overrides:
        cfg_kwargs.update(config_overrides)
    cfg = CfgClass(**cfg_kwargs)
    strategy = StratClass(cfg)

    # Simulation state
    equity = initial_equity
    peak_equity = initial_equity
    max_drawdown = 0.0
    trades: list[dict] = []
    pnl_curve = [equity]
    in_position = False
    entry_price = 0.0

    leverage = getattr(cfg, "leverage", 1.0)
    size_pct = getattr(cfg, "position_size_pct", 0.2)
    fee_bps = 5  # 0.05% taker fee

    for _, row in df.iterrows():
        candle = {
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row.get("volume", 0)),
            "timestamp": str(row["open_time"]),
        }
        current_price = candle["close"]

        if hasattr(strategy, "on_candle"):
            strategy.on_candle(candle)

        if not in_position:
            signal = strategy.get_signal() if hasattr(strategy, "get_signal") else None
            if signal == "buy":
                entry_price = current_price
                size_usd = equity * size_pct * leverage
                fee = size_usd * fee_bps / 10000
                equity -= fee
                in_position = True
                if hasattr(strategy, "on_fill"):
                    strategy.on_fill("buy", entry_price, f"t_{len(trades)}")
        else:
            exit_reason = strategy.get_exit_signal(current_price) if hasattr(strategy, "get_exit_signal") else None
            if exit_reason:
                pnl_pct = (current_price - entry_price) / entry_price * leverage
                size_usd = equity * size_pct * leverage
                pnl_usd = size_usd * pnl_pct
                fee = size_usd * fee_bps / 10000
                equity += pnl_usd - fee
                trades.append({
                    "exit_reason": exit_reason,
                    "pnl_usd": pnl_usd - fee,
                    "won": pnl_usd > 0,
                })
                in_position = False
                entry_price = 0.0
                if hasattr(strategy, "on_fill"):
                    strategy.on_fill("sell", current_price, f"t_{len(trades)}")

        # Equity tracking
        unrealized = 0.0
        if in_position:
            size_usd = equity * size_pct * leverage
            unrealized = size_usd * (current_price - entry_price) / entry_price

        current_equity = equity + unrealized
        pnl_curve.append(round(current_equity, 2))
        if current_equity > peak_equity:
            peak_equity = current_equity
        dd = (peak_equity - current_equity) / peak_equity * 100
        if dd > max_drawdown:
            max_drawdown = dd

    # Final close
    if in_position and entry_price:
        last_price = df.iloc[-1]["close"]
        pnl_pct = (last_price - entry_price) / entry_price * leverage
        size_usd = equity * size_pct * leverage
        equity += size_usd * pnl_pct

    # Metrics
    total_return_pct = (equity - initial_equity) / initial_equity * 100
    n = len(pnl_curve)
    returns = [(pnl_curve[i] - pnl_curve[i-1]) / pnl_curve[i-1] for i in range(1, n) if pnl_curve[i-1] != 0]
    if returns:
        import statistics
        mean_r = statistics.mean(returns)
        std_r = statistics.stdev(returns) if len(returns) > 1 else 0.0001
        sharpe = (mean_r / std_r) * (252 ** 0.5) if std_r > 0 else 0.0
    else:
        sharpe = 0.0

    wins = [t for t in trades if t["won"]]
    losses = [t for t in trades if not t["won"]]
    win_rate = len(wins) / len(trades) * 100 if trades else 0.0
    gross_profit = sum(t["pnl_usd"] for t in wins)
    gross_loss = abs(sum(t["pnl_usd"] for t in losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (9.99 if gross_profit > 0 else 0.0)
    avg_trade = sum(t["pnl_usd"] for t in trades) / len(trades) if trades else 0.0

    elapsed_ms = int((time.time() - t0) * 1000)

    # Downsample pnl_curve to 200 points for display
    step = max(1, len(pnl_curve) // 200)
    pnl_curve_sampled = [round(v, 2) for v in pnl_curve[::step]]

    return BacktestResult(
        strategy=strategy_name,
        ticker=ticker,
        days=days,
        initial_equity=initial_equity,
        final_equity=round(equity, 2),
        total_return_pct=round(total_return_pct, 2),
        sharpe_ratio=round(sharpe, 3),
        max_drawdown_pct=round(max_drawdown, 2),
        win_rate=round(win_rate, 1),
        total_trades=len(trades),
        profit_factor=round(profit_factor, 2),
        avg_trade_pnl=round(avg_trade, 2),
        pnl_curve=pnl_curve_sampled,
        elapsed_ms=elapsed_ms,
    )


# ── CLI ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="ClawSwap local backtest")
    parser.add_argument("--strategy", default="mean_reversion",
                        choices=list(STRATEGY_MAP.keys()))
    parser.add_argument("--ticker", default="BTC")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--equity", type=float, default=10_000.0)
    parser.add_argument("--config", default="{}", help="JSON config overrides")
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--json", action="store_true", help="Output JSON result")
    args = parser.parse_args()

    config_overrides = json.loads(args.config) if args.config else {}
    data_dir = Path(args.data_dir) if args.data_dir else None

    try:
        result = run_backtest(
            strategy_name=args.strategy,
            ticker=args.ticker,
            days=args.days,
            initial_equity=args.equity,
            config_overrides=config_overrides,
            data_dir=data_dir,
        )
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    if args.json:
        print(json.dumps(result.__dict__))
        return

    sign = "+" if result.total_return_pct >= 0 else ""
    print(f"""
╔══ BACKTEST RESULTS ═══════════════════════════╗
  Strategy    : {result.strategy}
  Ticker      : {result.ticker}
  Period      : {result.days} days ({result.total_trades} trades)
  
  Return      : {sign}{result.total_return_pct}%
  Sharpe      : {result.sharpe_ratio}
  Max DD      : -{result.max_drawdown_pct}%
  Win Rate    : {result.win_rate}%
  Profit Fac. : {result.profit_factor}
  Avg Trade   : ${result.avg_trade_pnl:,.2f}
  
  Initial Eq  : ${result.initial_equity:,.2f}
  Final Eq    : ${result.final_equity:,.2f}
  Elapsed     : {result.elapsed_ms}ms
╚═══════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    main()
