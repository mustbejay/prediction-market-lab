#!/usr/bin/env python3
"""Live opportunity scanner for H7, H2, H3 strategies."""

import json
import sys
import time
import urllib.request
import urllib.parse
import re
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict
import statistics

# API endpoints
POLYMARKET_GAMMA = "https://gamma-api.polymarket.com/public-search"
POLYMARKET_TRADES = "https://data-api.polymarket.com/trades"
UA = "predictions-lab/0.1 (+scanner)"

# Strategy thresholds
STRATEGIES = {
    "H7_high": {"range": (0.50, 0.60), "side": "Up", "weight": 0.4},
    "H7_low": {"range": (0.40, 0.50), "side": "Up", "weight": 0.3},
    "H2": {"threshold": 0.70, "lookback": 3, "weight": 0.3},
    "H3": {"min_move": 0.12, "weight": 0.2},
}

# Regex for Up/Down slugs
UPDOWN_PATTERN = re.compile(r"-(?:btc|eth|sol|xrp)-updown-(5m|15m|1h|4h|1d)-(\d{10})$", re.IGNORECASE)


def fetch_markets(query: str, limit: int = 20) -> list[dict]:
    """Fetch markets from Polymarket Gamma API."""
    url = f"{POLYMARKET_GAMMA}?q={urllib.parse.quote(query)}&limit_per_type={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            return data.get("events", [])
    except Exception as e:
        print(f"API error: {e}", file=sys.stderr)
        return []


def fetch_price_history(condition_id: str, limit: int = 100) -> list[dict]:
    """Fetch recent price data for a condition."""
    url = f"{POLYMARKET_TRADES}?conditionId={condition_id}&limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            if isinstance(data, list):
                return data
            return []
    except Exception:
        return []


def analyze_opportunity(market: dict) -> dict | None:
    """Analyze a market for strategy opportunities."""
    slug = market.get("slug", "").lower()
    match = UPDOWN_PATTERN.search(slug)
    if not match:
        return None

    timeframe = match.group(1)
    condition_id = market.get("conditionId", "")
    prices = market.get("outcomePrices", []) or market.get("prices", [])
    title = market.get("question", "")

    if len(prices) < 1:
        return None

    try:
        p0 = float(prices[0])
    except (TypeError, ValueError):
        return None

    opportunities = []

    # H7: 0.5 discontinuity
    if 0.50 <= p0 < 0.60:
        opportunities.append({
            "strategy": "H7_high",
            "confidence": 0.8,
            "entry": p0,
            "side": "Up",
            "reason": f"p(Up)={p0:.3f} in [0.5, 0.6)",
        })
    elif 0.40 <= p0 < 0.50:
        opportunities.append({
            "strategy": "H7_low",
            "confidence": 0.6,
            "entry": p0,
            "side": "Up",
            "reason": f"p(Up)={p0:.3f} in [0.4, 0.5)",
        })

    # H2: Late favourite (would need price history to confirm)
    # H3: Momentum (would need price history to confirm)

    return {
        "condition_id": condition_id,
        "title": title,
        "timeframe": timeframe,
        "current_price": p0,
        "opportunities": opportunities,
        "score": sum(o["confidence"] * o["weight"] for o in opportunities),
    }


def run_scanner(limit_per_asset: int = 10, sleep_ms: int = 500):
    """Run live scanner loop."""
    assets = ["btc", "eth", "sol", "xrp"]
    queries = [f"{a} updown {tf}" for a in assets for tf in ["5m", "15m"]]

    print("=" * 60)
    print("TREND INTEL LIVE SCANNER")
    print(f"Strategies: H7 (0.5 discontinuity), H2 (late fav), H3 (momentum)")
    print(f"Assets: {', '.join(assets)} | Timeframes: 5m, 15m")
    print("=" * 60)
    print(f"\nScanning... press Ctrl+C to stop\n")

    seen_conditions: set[str] = set()
    last_scan_time = 0

    try:
        while True:
            now = datetime.now(timezone.utc)
            scan_num = len(seen_conditions) // 10 + 1
            print(f"[{now.strftime('%H:%M:%S')}] Scan #{scan_num}...", end=" ", flush=True)

            new_opportunities = []

            for query in queries:
                events = fetch_markets(query, limit_per_asset)
                for event in events:
                    for market in event.get("markets", []):
                        cond_id = market.get("conditionId", "")
                        if cond_id in seen_conditions:
                            continue
                        seen_conditions.add(cond_id)

                        analysis = analyze_opportunity(market)
                        if analysis and analysis["opportunities"]:
                            new_opportunities.append(analysis)

            if new_opportunities:
                print(f"Found {len(new_opportunities)} opportunities!")
                for opp in new_opportunities[:5]:
                    print(f"\n  📍 {opp['title'][:50]}...")
                    print(f"     Asset: {opp['timeframe']} | Price: {opp['current_price']:.3f}")
                    for o in opp["opportunities"]:
                        print(f"     → {o['strategy']}: {o['reason']} (confidence: {o['confidence']:.2f})")
            else:
                print(f"No new opportunities ({len(seen_conditions)} markets seen)")

            time.sleep(sleep_ms / 1000)

    except KeyboardInterrupt:
        print(f"\n\nScanner stopped. Total markets scanned: {len(seen_conditions)}")
        return seen_conditions


if __name__ == "__main__":
    run_scanner()
