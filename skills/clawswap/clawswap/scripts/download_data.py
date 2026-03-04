#!/usr/bin/env python3
"""
ClawSwap — Local Backtest Data Downloader
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Downloads 15-minute candle data from data.binance.vision (static ZIPs).
Stores locally for offline backtesting — no API calls at backtest runtime.

Usage:
    python download_data.py                    # downloads BTC, ETH, SOL (last 90 days)
    python download_data.py --tickers BTC ETH  # specific tickers
    python download_data.py --days 30          # fewer days
    python download_data.py --data-dir ./data  # custom output dir
"""

import argparse
import io
import os
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    print("Missing dependency: pip install requests")
    sys.exit(1)

try:
    import pandas as pd
except ImportError:
    print("Missing dependency: pip install pandas")
    sys.exit(1)


# ── Config ────────────────────────────────────────────────────────────────

BINANCE_BASE = "https://data.binance.vision/data/futures/um/monthly/klines"
INTERVAL = "15m"
TICKERS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
DEFAULT_DAYS = 90
CHUNK_COLS = ["open_time", "open", "high", "low", "close", "volume",
              "close_time", "quote_volume", "trades",
              "taker_buy_base", "taker_buy_quote", "ignore"]


def ticker_to_symbol(ticker: str) -> str:
    """BTC → BTCUSDT"""
    t = ticker.upper()
    if not t.endswith("USDT"):
        t = t + "USDT"
    return t


def download_month(symbol: str, year: int, month: int, data_dir: Path) -> bool:
    """Download and extract one monthly ZIP. Returns True if successful."""
    fname = f"{symbol}-{INTERVAL}-{year}-{month:02d}.zip"
    url = f"{BINANCE_BASE}/{symbol}/{INTERVAL}/{fname}"
    out_csv = data_dir / f"{symbol}-{INTERVAL}-{year}-{month:02d}.csv"

    if out_csv.exists():
        print(f"  ✓ {fname} already cached")
        return True

    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 404:
            return False
        r.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            csv_name = zf.namelist()[0]
            with zf.open(csv_name) as f:
                df = pd.read_csv(f, header=None, names=CHUNK_COLS)
                df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
                df = df[["open_time", "open", "high", "low", "close", "volume"]]
                df.to_csv(out_csv, index=False)
        print(f"  ↓ {fname} → {out_csv.name}")
        return True
    except requests.RequestException as e:
        print(f"  ✗ {fname}: {e}")
        return False


def merge_csvs(symbol: str, data_dir: Path, days: int) -> Path:
    """Merge monthly CSVs into a single file for the last N days."""
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    parts = sorted(data_dir.glob(f"{symbol}-{INTERVAL}-*.csv"))
    if not parts:
        raise FileNotFoundError(f"No data files for {symbol}")

    dfs = []
    for p in parts:
        try:
            df = pd.read_csv(p, parse_dates=["open_time"])
            dfs.append(df)
        except Exception:
            pass

    combined = pd.concat(dfs, ignore_index=True)
    combined["open_time"] = pd.to_datetime(combined["open_time"], utc=True)
    combined = combined[combined["open_time"] >= cutoff]
    combined = combined.sort_values("open_time").drop_duplicates("open_time")

    out = data_dir / f"{symbol}-{INTERVAL}-merged-{days}d.csv"
    combined.to_csv(out, index=False)
    print(f"  → Merged {len(combined)} candles → {out.name}")
    return out


def download_ticker(ticker: str, data_dir: Path, days: int) -> bool:
    symbol = ticker_to_symbol(ticker)
    print(f"\n[{symbol}]")
    data_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(tz=timezone.utc)
    months_needed = max(1, days // 28 + 1)
    success = False
    for i in range(months_needed):
        dt = now - timedelta(days=30 * i)
        ok = download_month(symbol, dt.year, dt.month, data_dir)
        if ok:
            success = True

    if success:
        merge_csvs(symbol, data_dir, days)
    return success


def main() -> None:
    parser = argparse.ArgumentParser(description="Download ClawSwap backtest data")
    parser.add_argument("--tickers", nargs="+", default=["BTC", "ETH", "SOL"])
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--data-dir", default="./data/candles")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    print(f"ClawSwap Backtest Data Downloader")
    print(f"Tickers : {', '.join(args.tickers)}")
    print(f"Days    : {args.days}")
    print(f"Output  : {data_dir.resolve()}")
    print("=" * 50)

    ok_count = 0
    for ticker in args.tickers:
        if download_ticker(ticker, data_dir, args.days):
            ok_count += 1

    print(f"\n✓ Done: {ok_count}/{len(args.tickers)} tickers ready")
    print(f"Run backtest with: python scripts/backtest.py --ticker BTC --days {args.days}")


if __name__ == "__main__":
    main()
