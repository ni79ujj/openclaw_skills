#!/usr/bin/env python3
"""
ClawSwap Self-Hosted Agent Runner
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Runs your trading strategy 24/7 and streams telemetry to ClawSwap Arena.
Handles: strategy execution · heartbeat · position tracking · Arena visibility.

Usage:
    python agent.py --strategy mean_reversion --ticker BTC --mode arena
    python agent.py --strategy momentum --ticker ETH --mode live
    python agent.py --config agent_config.json

Config file (agent_config.json):
    {
        "name": "My BTC Hunter",
        "strategy": "mean_reversion",
        "ticker": "BTC",
        "mode": "arena",          # arena | competition | live
        "wallet": "0x...",
        "private_key": "...",     # or set CLAWSWAP_PRIVATE_KEY env var
        "gateway_url": "https://gateway.clawswap.trade",
        "strategy_config": {
            "leverage": 2.0,
            "entry_drop_pct": 2.0
        }
    }
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    import httpx
except ImportError:
    print("Missing: pip install httpx")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent.parent))
from strategies import STRATEGY_MAP

# ── Logging ────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("agent.log"),
    ],
)
log = logging.getLogger("clawswap.agent")


# ── Config ─────────────────────────────────────────────────────────────────

GATEWAY_URL = os.environ.get("CLAWSWAP_GATEWAY_URL", "https://gateway.clawswap.trade")
HEARTBEAT_INTERVAL = 30        # seconds
CANDLE_POLL_INTERVAL = 60      # seconds (1m polling for 15m candles)
TELEMETRY_INTERVAL = 30        # seconds


@dataclass
class AgentConfig:
    name: str = "ClawSwap Agent"
    strategy: str = "mean_reversion"
    ticker: str = "BTC"
    mode: str = "arena"                 # arena | competition | live
    wallet: str = ""
    private_key: str = ""
    gateway_url: str = GATEWAY_URL
    competition_id: Optional[str] = None
    strategy_config: dict = None

    def __post_init__(self):
        if self.strategy_config is None:
            self.strategy_config = {}
        if not self.private_key:
            self.private_key = os.environ.get("CLAWSWAP_PRIVATE_KEY", "")
        if not self.wallet:
            self.wallet = os.environ.get("CLAWSWAP_WALLET", "")


@dataclass
class AgentState:
    agent_id: str = ""
    agent_token: str = ""
    equity: float = 10_000.0
    pnl_pct: float = 0.0
    total_trades: int = 0
    win_trades: int = 0
    positions: list = None
    last_price: float = 0.0
    started_at: str = ""

    def __post_init__(self):
        if self.positions is None:
            self.positions = []
        if not self.started_at:
            self.started_at = datetime.now(tz=timezone.utc).isoformat()

    @property
    def win_rate(self) -> float:
        return (self.win_trades / self.total_trades * 100) if self.total_trades > 0 else 0.0


# ── API Client ─────────────────────────────────────────────────────────────

class ClawSwapAPI:
    def __init__(self, cfg: AgentConfig, state: AgentState):
        self.cfg = cfg
        self.state = state
        self.client = httpx.AsyncClient(timeout=15.0, base_url=cfg.gateway_url)

    async def register(self) -> bool:
        """Register self-hosted agent, get agent_id + token."""
        try:
            r = await self.client.post("/api/v1/agent/register", json={
                "name": self.cfg.name,
                "wallet": self.cfg.wallet,
                "strategy": self.cfg.strategy,
                "ticker": self.cfg.ticker,
                "mode": self.cfg.mode,
                "host_type": "self_hosted",
            })
            if r.status_code == 200:
                data = r.json()
                self.state.agent_id = data["agent_id"]
                self.state.agent_token = data["agent_token"]
                log.info(f"Registered: agent_id={self.state.agent_id}")
                return True
            else:
                log.error(f"Registration failed: {r.status_code} {r.text}")
                return False
        except Exception as e:
            log.error(f"Registration error: {e}")
            return False

    async def get_price(self) -> float:
        """Fetch latest price for the ticker."""
        try:
            r = await self.client.get(f"/api/v1/prices/{self.cfg.ticker}")
            if r.status_code == 200:
                return float(r.json().get("price", 0))
        except Exception:
            pass
        return 0.0

    async def send_telemetry(self) -> bool:
        """Push heartbeat + current state to Arena."""
        if not self.state.agent_id:
            return False
        payload = {
            "agent_id": self.state.agent_id,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "equity": self.state.equity,
            "pnl_pct": self.state.pnl_pct,
            "total_trades": self.state.total_trades,
            "win_rate": self.state.win_rate,
            "positions": self.state.positions,
            "last_price": self.state.last_price,
            "mode": self.cfg.mode,
            "ticker": self.cfg.ticker,
            "strategy": self.cfg.strategy,
        }
        try:
            r = await self.client.post(
                "/api/v1/agent/telemetry",
                json=payload,
                headers={"Authorization": f"Bearer {self.state.agent_token}"},
            )
            return r.status_code == 200
        except Exception as e:
            log.warning(f"Telemetry failed: {e}")
            return False

    async def submit_trade(self, side: str, size_usd: float, price: float, reason: str = "") -> Optional[str]:
        """Submit a trade to the paper engine (arena mode) or live (live mode)."""
        if self.cfg.mode == "arena":
            endpoint = "/api/v1/paper/trade"
        else:
            endpoint = "/api/v1/trade"

        try:
            r = await self.client.post(endpoint, json={
                "agent_id": self.state.agent_id,
                "ticker": self.cfg.ticker,
                "side": side,
                "size_usd": size_usd,
                "price": price,
                "reason": reason,
            }, headers={"Authorization": f"Bearer {self.state.agent_token}"})
            if r.status_code == 200:
                return r.json().get("trade_id")
        except Exception as e:
            log.error(f"Trade failed: {e}")
        return None

    async def close(self):
        await self.client.aclose()


# ── Agent Runner ───────────────────────────────────────────────────────────

class AgentRunner:
    def __init__(self, cfg: AgentConfig):
        self.cfg = cfg
        self.state = AgentState()
        self.api = ClawSwapAPI(cfg, self.state)
        self.running = False

        StratClass, CfgClass = STRATEGY_MAP[cfg.strategy]
        strat_cfg = CfgClass(ticker=cfg.ticker, **cfg.strategy_config)
        self.strategy = StratClass(strat_cfg)

        self.initial_equity = 10_000.0
        self.current_equity = self.initial_equity

    async def start(self):
        log.info(f"Starting agent: {self.cfg.name}")
        log.info(f"Strategy: {self.cfg.strategy} | Ticker: {self.cfg.ticker} | Mode: {self.cfg.mode}")

        # Register with ClawSwap
        ok = await self.api.register()
        if not ok:
            log.warning("Registration failed — running in offline mode (no Arena visibility)")

        self.running = True
        self.state.equity = self.initial_equity

        # Start tasks
        await asyncio.gather(
            self._price_loop(),
            self._telemetry_loop(),
        )

    async def _price_loop(self):
        """Main loop: fetch price → run strategy → execute if signal."""
        while self.running:
            try:
                price = await self.api.get_price()
                if price > 0:
                    self.state.last_price = price
                    await self._run_strategy_cycle(price)
            except Exception as e:
                log.error(f"Price loop error: {e}")
            await asyncio.sleep(CANDLE_POLL_INTERVAL)

    async def _run_strategy_cycle(self, price: float):
        """Feed price to strategy, execute trades if signal."""
        candle = {
            "open": price, "high": price, "low": price,
            "close": price, "volume": 0,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }

        if hasattr(self.strategy, "on_candle"):
            self.strategy.on_candle(candle)

        leverage = getattr(self.strategy.cfg, "leverage", 1.0)
        size_pct = getattr(self.strategy.cfg, "position_size_pct", 0.2)
        size_usd = self.current_equity * size_pct * leverage

        in_position = len(self.state.positions) > 0

        if not in_position:
            signal = self.strategy.get_signal() if hasattr(self.strategy, "get_signal") else None
            if signal == "buy":
                trade_id = await self.api.submit_trade("buy", size_usd, price, "entry")
                if trade_id:
                    self.state.positions = [{"trade_id": trade_id, "entry": price, "size_usd": size_usd}]
                    self.strategy.on_fill("buy", price, trade_id)
                    log.info(f"BUY {self.cfg.ticker} @ {price:.2f} (${size_usd:.0f})")
        else:
            exit_signal = self.strategy.get_exit_signal(price) if hasattr(self.strategy, "get_exit_signal") else None
            if exit_signal:
                pos = self.state.positions[0]
                entry = pos["entry"]
                pnl_pct = (price - entry) / entry * leverage
                pnl_usd = pos["size_usd"] * pnl_pct
                self.current_equity += pnl_usd
                self.state.total_trades += 1
                if pnl_usd > 0:
                    self.state.win_trades += 1
                self.state.equity = self.current_equity
                self.state.pnl_pct = (self.current_equity - self.initial_equity) / self.initial_equity * 100
                self.state.positions = []
                await self.api.submit_trade("sell", pos["size_usd"], price, exit_signal)
                self.strategy.on_fill("sell", price, pos["trade_id"])
                log.info(f"SELL {self.cfg.ticker} @ {price:.2f} | PnL: ${pnl_usd:+.2f} ({exit_signal})")

    async def _telemetry_loop(self):
        """Send heartbeat + state to Arena every 30s."""
        while self.running:
            ok = await self.api.send_telemetry()
            if ok:
                log.debug("Telemetry sent ✓")
            await asyncio.sleep(TELEMETRY_INTERVAL)

    def stop(self):
        log.info("Stopping agent...")
        self.running = False


# ── Entry Point ─────────────────────────────────────────────────────────────

def load_config(args) -> AgentConfig:
    cfg = AgentConfig()

    # Load from JSON config file if provided
    if args.config:
        with open(args.config) as f:
            data = json.load(f)
        cfg = AgentConfig(**data)

    # CLI overrides
    if args.strategy:
        cfg.strategy = args.strategy
    if args.ticker:
        cfg.ticker = args.ticker
    if args.mode:
        cfg.mode = args.mode
    if args.name:
        cfg.name = args.name

    return cfg


async def run(cfg: AgentConfig):
    runner = AgentRunner(cfg)

    def _shutdown(sig, frame):
        log.info(f"Signal {sig} received — shutting down")
        runner.stop()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    await runner.start()
    await runner.api.close()


def main():
    parser = argparse.ArgumentParser(description="ClawSwap Self-Hosted Agent")
    parser.add_argument("--config", help="Path to agent_config.json")
    parser.add_argument("--strategy", choices=list(STRATEGY_MAP.keys()), default=None)
    parser.add_argument("--ticker", default=None)
    parser.add_argument("--mode", choices=["arena", "competition", "live"], default=None)
    parser.add_argument("--name", default=None)
    args = parser.parse_args()

    if not args.config and not args.strategy:
        print("Error: provide --config or --strategy")
        print("Example: python agent.py --strategy mean_reversion --ticker BTC --mode arena")
        sys.exit(1)

    cfg = load_config(args)

    if not cfg.wallet and not cfg.private_key:
        print("Error: set CLAWSWAP_WALLET and CLAWSWAP_PRIVATE_KEY env vars")
        sys.exit(1)

    log.info("=" * 50)
    log.info(f"ClawSwap Self-Hosted Agent v0.2.0")
    log.info(f"Name    : {cfg.name}")
    log.info(f"Strategy: {cfg.strategy}")
    log.info(f"Ticker  : {cfg.ticker}")
    log.info(f"Mode    : {cfg.mode}")
    log.info(f"Gateway : {cfg.gateway_url}")
    log.info("=" * 50)

    asyncio.run(run(cfg))


if __name__ == "__main__":
    main()
