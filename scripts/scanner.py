#!/usr/bin/env python3
"""Fee comparison and live scanner for prediction markets."""

import json
import sys
import time
import urllib.request
import urllib.parse
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple


# ============================================================================
# FEE STRUCTURE COMPARISON
# ============================================================================

class VenueFees(NamedTuple):
    venue: str
    taker_fee_bps: int | None
    maker_rebate_bps: int | None
    pair_cost_premium: float
    net_edge: dict[str, float]


def compare_fees():
    """Compare fee structures across venues."""
    # Limitless fees (from snapshot analysis)
    limitless_fees = VenueFees(
        venue="Limitless",
        taker_fee_bps=75,  # typical CLOB fee
        maker_rebate_bps=0,
        pair_cost_premium=8.5,  # median pair cost 1.085
        net_edge={
            "H7_high": 0.0636,  # 0.0677 - fee
            "H2": 0.0184,
            "H3": 0.0180,
        }
    )

    # Polymarket fees (from wallet analysis)
    polymarket_fees = VenueFees(
        venue="Polymarket",
        taker_fee_bps=None,  # built into spread
        maker_rebate_bps=None,
        pair_cost_premium=-17.0,  # median pair cost 0.83 (discount!)
        net_edge={
            "H7_high": 0.0663,  # 0.0677 * 0.98
            "H2": 0.0220,
            "H3": 0.0217,
        }
    )

    # Print comparison
    print("\n" + "=" * 80)
    print("VENUE FEE COMPARISON")
    print("=" * 80)

    print(f"\n{'Metric':<35} {'Limitless':<20} {'Polymarket':<20}")
    print("-" * 80)
    print(f"{'Taker fee (bps)':<35} {limitless_fees.taker_fee_bps or 'N/A':<20} {'Built-in (2% win tax)':<20}")
    print(f"{'Maker rebate (bps)':<35} {limitless_fees.maker_rebate_bps or 'N/A':<20} {'None':<20}")
    print(f"{'Pair cost premium (%)':<35} {limitless_fees.pair_cost_premium:<20.1f} {polymarket_fees.pair_cost_premium:<20.1f}")
    print(f"{'Arb opportunity':<35} {'None (premium > 0)':<20} {'Abundant (discount < 0)':<20}")

    print("\n" + "-" * 80)
    print("NET EDGE AFTER FEES (per share):")
    print("-" * 80)
    print(f"{'Strategy':<20} {'Limitless':<15} {'Polymarket':<15} {'Winner':<15}")
    print("-" * 80)

    for strategy in ["H7_high", "H2", "H3"]:
        lim_net = limitless_fees.net_edge[strategy]
        poly_net = polymarket_fees.net_edge[strategy]
        winner = "Limitless" if lim_net > poly_net else "Polymarket"
        print(f"{strategy:<20} {lim_net:>+12.4f} {poly_net:>+12.4f} {winner:<15}")

    print("\n" + "=" * 80)
    print("KEY INSIGHTS:")
    print("=" * 80)
    print("""
1. LIMITLESS:
   - Pair cost PREMIUM of 8.5% (buying both sides costs 1.085)
   - Explicit taker fee: ~0.75% per trade
   - Net edge: strategies must overcome ~1.5% round-trip cost
   - Best for: Directional momentum plays (H2, H3)

2. POLYMARKET:
   - Pair cost DISCOUNT of 17% (buying both sides costs 0.83)
   - Implicit "fee": 2% tax on winning positions
   - Net edge: strategies benefit from natural arbitrage
   - Best for: Hedging strategies, pair cost arb

3. RECOMMENDATION:
   - For H7/H2/H3 momentum strategies: Use LIMITLESS
   - For pair cost arbitrage: Use POLYMARKET
   - For hedging: POLYMARKET has natural discount
""")


# ============================================================================
# LIVE SCANNER
# ============================================================================

UPDOWN_PATTERN = re.compile(r"-(?:btc|eth|sol|xrp)-updown-(5m|15m|1h|4h|1d)-(\d{10})$", re.IGNORECASE)

STRATEGY_THRESHOLDS = {
    "H7_high": {"p_range": (0.50, 0.60), "side": "Up", "min_confidence": 0.7},
    "H7_low": {"p_range": (0.40, 0.50), "side": "Up", "min_confidence": 0.5},
    "H2": {"threshold": 0.70, "lookback": 3},
    "H3": {"min_move": 0.12},
}


def fetch_markets(query: str, limit: int = 20) -> list[dict]:
    """Fetch markets from Polymarket."""
    url = f"https://gamma-api.polymarket.com/public-search?q={urllib.parse.quote(query)}&limit_per_type={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "predictions-lab/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            return data.get("events", [])
    except Exception as e:
        print(f"API error: {e}", file=sys.stderr)
        return []


def analyze_market(market: dict) -> dict | None:
    """Analyze a market for opportunities."""
    slug = market.get("slug", "").lower()
    match = UPDOWN_PATTERN.search(slug)
    if not match:
        return None

    timeframe = match.group(1)
    condition_id = market.get("conditionId", "")
    prices = market.get("outcomePrices", []) or market.get("prices", [])
    title = market.get("question", "")

    if not prices or len(prices) < 1:
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
            "expected_edge": 0.064,  # from backtest
        })
    elif 0.40 <= p0 < 0.50:
        opportunities.append({
            "strategy": "H7_low",
            "confidence": 0.5,
            "entry": p0,
            "side": "Up",
            "expected_edge": -0.107,  # negative edge
        })

    if not opportunities:
        return None

    return {
        "condition_id": condition_id,
        "title": title[:60],
        "timeframe": timeframe,
        "current_price": p0,
        "opportunities": opportunities,
        "venue": "Polymarket",
    }


def run_scanner(limit_per_asset: int = 10, max_runs: int = 5):
    """Run live scanner."""
    assets = ["btc", "eth", "sol", "xrp"]
    timeframes = ["5m", "15m"]
    queries = [f"{a} updown {tf}" for a in assets for tf in timeframes]

    print("=" * 80)
    print("TREND INTEL LIVE SCANNER")
    print("=" * 80)
    print(f"Strategies: H7 (0.5 discontinuity)")
    print(f"Assets: {', '.join(assets)} | Timeframes: {', '.join(timeframes)}")
    print("=" * 80)
    print()

    seen_conditions: set[str] = set()
    all_opportunities: list[dict] = []

    for run in range(1, max_runs + 1):
        now = datetime.now(timezone.utc)
        print(f"[{now.strftime('%H:%M:%S')}] Scan #{run}/{max_runs}...", end=" ", flush=True)

        new_opps = []
        for query in queries:
            events = fetch_markets(query, limit_per_asset)
            for event in events:
                for market in event.get("markets", []):
                    cond_id = market.get("conditionId", "")
                    if cond_id in seen_conditions:
                        continue
                    seen_conditions.add(cond_id)

                    analysis = analyze_market(market)
                    if analysis:
                        new_opps.append(analysis)

        if new_opps:
            print(f"Found {len(new_opps)} opportunities!")
            all_opportunities.extend(new_opps)
            for opp in new_opps[:3]:
                print(f"\n  📍 {opp['title']}")
                print(f"     {opp['venue']} | {opp['timeframe']} | p={opp['current_price']:.3f}")
                for o in opp['opportunities']:
                    edge = o.get('expected_edge', 0)
                    sign = "+" if edge > 0 else ""
                    print(f"     → {o['strategy']}: entry={o['entry']:.3f} {o['side']} (edge={sign}{edge:.3f})")
        else:
            print(f"No new opportunities ({len(seen_conditions)} markets scanned)")

        if run < max_runs:
            time.sleep(2)

    print("\n" + "=" * 80)
    print(f"SCAN COMPLETE: {len(seen_conditions)} markets, {len(all_opportunities)} opportunities")
    print("=" * 80)

    return all_opportunities


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Prediction Market Scanner")
    parser.add_argument("--compare", action="store_true", help="Show fee comparison only")
    parser.add_argument("--runs", type=int, default=3, help="Number of scan runs")
    args = parser.parse_args()

    if args.compare:
        compare_fees()
    else:
        run_scanner(max_runs=args.runs)
