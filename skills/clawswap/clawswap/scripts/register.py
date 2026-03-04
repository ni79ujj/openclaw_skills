#!/usr/bin/env python3
"""
One-time registration of a self-hosted ClawSwap agent.

Usage:
  python register.py --config config.yaml [--name "My Agent"]
"""

import argparse
import json
import os
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import yaml


def register(config: dict, name: str | None = None) -> dict:
    gateway_url = config.get("gateway_url", "https://gateway.clawswap.trade").rstrip("/")
    wallet = config.get("wallet_address", "")
    agent_name = name or config.get("agent_name", f"SelfHosted-{wallet[:6]}")
    strategy = config.get("strategy", "mean_reversion")
    ticker = config.get("ticker", "BTC")
    mode = config.get("mode", "arena")

    if not wallet or not wallet.startswith("0x"):
        print("❌ wallet_address must start with 0x")
        sys.exit(1)

    payload = json.dumps({
        "wallet": wallet,
        "name": agent_name,
        "strategy": strategy,
        "ticker": ticker,
        "mode": mode,
        "hosting": "self_hosted",
    }).encode()

    req = Request(
        f"{gateway_url}/api/v1/agents/register",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(req, timeout=30) as resp:
            data = json.load(resp)
    except HTTPError as e:
        body = e.read().decode()
        print(f"❌ Registration failed ({e.code}): {body}")
        sys.exit(1)

    return data


def save_token(config_path: str, agent_token: str, agent_id: str) -> None:
    """Save agent_token to a separate .agent file next to config."""
    token_path = config_path.replace(".yaml", ".agent")
    with open(token_path, "w") as f:
        json.dump({"agent_token": agent_token, "agent_id": agent_id}, f)
    os.chmod(token_path, 0o600)
    print(f"✅ Token saved to {token_path}")


def main():
    parser = argparse.ArgumentParser(description="Register a self-hosted ClawSwap agent")
    parser.add_argument("--config", default="config.yaml", help="Config YAML path")
    parser.add_argument("--name", help="Override agent display name")
    args = parser.parse_args()

    config_path = os.path.abspath(args.config)
    if not os.path.exists(config_path):
        print(f"❌ Config not found: {config_path}")
        print("   Copy config.example.yaml → config.yaml and fill in your values.")
        sys.exit(1)

    with open(config_path) as f:
        config = yaml.safe_load(f)

    print(f"🔗 Registering agent with {config.get('gateway_url', 'https://gateway.clawswap.trade')} ...")
    result = register(config, args.name)

    agent_id = result.get("agent_id", "")
    agent_token = result.get("agent_token", "")
    agent_name = result.get("name", "")

    print(f"✅ Registered: {agent_name} (ID: {agent_id})")
    print(f"   Mode: {config.get('mode', 'arena')}")
    print(f"   Strategy: {config.get('strategy', 'mean_reversion')} on {config.get('ticker', 'BTC')}")
    print()

    save_token(config_path, agent_token, agent_id)

    print("🚀 Next: launch the agent with:")
    print(f"   python agent.py --config {config_path}")


if __name__ == "__main__":
    main()
