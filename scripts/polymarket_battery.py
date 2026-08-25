#!/usr/bin/env python3
"""Hypothesis battery for Polymarket wallet data."""

import json
import sys
from pathlib import Path
from collections import defaultdict
import statistics

SNAPSHOT_DIR = Path(__file__).parent.parent / "data"
WALLET_FILE = SNAPSHOT_DIR / "wallet-ce25-sample.json"


def load_wallet_data():
    """Load wallet trade history."""
    with open(WALLET_FILE) as f:
        data = json.load(f)
    return data


def extract_market_lifecycles(data):
    """Extract market lifecycles from trade history."""
    markets = data.get("markets", [])
    trades = data.get("trade_rows", [])

    # Group trades by market
    market_trades = defaultdict(list)
    raw_trades = data.get("trade_rows", [])
    if isinstance(raw_trades, int):
        raw_trades = []
    for t in raw_trades:
        mid = t.get("market_id") or t.get("condition_id")
        if mid:
            market_trades[mid].append(t)

    # Analyze each market
    lifecycles = []
    for m in markets:
        mid = m.get("id") or m.get("condition_id")
        if not mid:
            continue

        title = m.get("title", "")
        if "up or down" not in title.lower():
            continue

        # Get trades for this market
        trades = sorted(market_trades.get(mid, []), key=lambda t: t.get("timestamp", 0))
        if len(trades) < 2:
            continue

        # Determine winner from final price
        final_prices = m.get("prices", [0.5, 0.5])
        winner = "Up" if final_prices[0] > 0.95 else ("Down" if final_prices[0] < 0.05 else None)

        if not winner:
            continue

        # Extract price series
        prices = []
        for t in trades:
            p = t.get("price")
            if p is not None:
                try:
                    prices.append(float(p))
                except (TypeError, ValueError):
                    pass

        if not prices:
            continue

        lifecycles.append({
            "id": mid,
            "title": title,
            "winner": winner,
            "prices": prices,
            "trades": trades,
            "start_price": prices[0],
            "end_price": prices[-1],
            "max_price": max(prices),
            "min_price": min(prices),
        })

    return lifecycles


def classify_asset(title):
    """Classify by asset."""
    t = title.lower()
    for sym in ("btc", "eth", "sol", "xrp"):
        if t.startswith(sym):
            return sym.upper()
    return None


def pnl_buy(side, price, winner):
    """P&L per share."""
    won = (winner == side)
    return (1.0 - price) if won else -price


def run_polymarket_battery(lcs):
    """Run hypothesis battery on Polymarket data."""
    print("\n" + "=" * 60)
    print("POLYMARKET WALLET ANALYSIS")
    print("=" * 60)
    print(f"Total Up/Down markets: {len(lcs)}")

    # Overall stats
    all_costs = []
    all_switches = []
    for lc in lcs:
        # Calculate pair cost from trade data
        buys = [t for t in lc["trades"] if t.get("side") == "buy"]
        if len(buys) >= 2:
            up_cost = sum(float(t.get("price", 0)) * float(t.get("size", 1)) for t in buys if t.get("outcome") == "up") / sum(float(t.get("size", 1)) for t in buys if t.get("outcome") == "up") if any(t.get("outcome") == "up" for t in buys) else 0
            dn_cost = sum(float(t.get("price", 0)) * float(t.get("size", 1)) for t in buys if t.get("side") == "buy" and t.get("outcome") == "down") / sum(float(t.get("size", 1)) for t in buys if t.get("side") == "buy" and t.get("outcome") == "down") if any(t.get("outcome") == "down" for t in buys) else 0
            if up_cost > 0 and dn_cost > 0:
                all_costs.append(up_cost + dn_cost)
        all_switches.append(lc.get("switches", 0))

    if all_costs:
        all_costs.sort()
        print(f"\nPair Cost Distribution:")
        print(f"  Median: {statistics.median(all_costs):.4f}")
        print(f"  Mean: {sum(all_costs)/len(all_costs):.4f}")
        below_95 = sum(1 for c in all_costs if c < 0.95)
        below_90 = sum(1 for c in all_costs if c < 0.90)
        print(f"  Below 0.95: {below_95} ({below_95/len(all_costs)*100:.1f}%)")
        print(f"  Below 0.90: {below_90} ({below_90/len(all_costs)*100:.1f}%)")

    # H7: 0.5 discontinuity
    print("\n--- H7: 0.5 Discontinuity ---")
    pnls_5_6 = []
    pnls_4_5 = []
    for lc in lcs:
        if len(lc["prices"]) < 2:
            continue
        start = lc["start_price"]
        if 0.50 <= start < 0.60:
            pnls_5_6.append(pnl_buy("Up", start, lc["winner"]))
        elif 0.40 <= start < 0.50:
            pnls_4_5.append(pnl_buy("Up", start, lc["winner"]))

    if pnls_5_6:
        tot = sum(pnls_5_6)
        hit = sum(1 for x in pnls_5_6 if x > 0)
        print(f"[H7] p(Up) in [0.5,0.6): n={len(pnls_5_6)} hit={hit/len(pnls_5_6)*100:.0f}% total={tot:+.2f} avg={tot/len(pnls_5_6):+.4f}/share")
    if pnls_4_5:
        tot = sum(pnls_4_5)
        hit = sum(1 for x in pnls_4_5 if x > 0)
        print(f"[H7] p(Up) in [0.4,0.5): n={len(pnls_4_5)} hit={hit/len(pnls_4_5)*100:.0f}% total={tot:+.2f} avg={tot/len(pnls_4_5):+.4f}/share")

    # H2: Late favourite
    print("\n--- H2: Late Favourite ---")
    pnls_late = []
    for lc in lcs:
        if len(lc["prices"]) < 3:
            continue
        penultimate = lc["prices"][-2]
        if penultimate >= 0.70:
            pnls_late.append(pnl_buy("Up", penultimate, lc["winner"]))
    if pnls_late:
        tot = sum(pnls_late)
        hit = sum(1 for x in pnls_late if x > 0)
        print(f"[H2] late fav (p>=0.70): n={len(pnls_late)} hit={hit/len(pnls_late)*100:.0f}% total={tot:+.2f} avg={tot/len(pnls_late):+.4f}/share")

    # H3: Momentum
    print("\n--- H3: Momentum ---")
    pnls_mom = []
    for lc in lcs:
        if len(lc["prices"]) < 4:
            continue
        p0 = lc["prices"][0]
        p_mid = lc["prices"][len(lc["prices"])//2]
        d = p_mid - p0
        if abs(d) >= 0.12:
            side = "Up" if d > 0 else "Down"
            entry = p_mid
            pnls_mom.append(pnl_buy(side, entry, lc["winner"]))
    if pnls_mom:
        tot = sum(pnls_mom)
        hit = sum(1 for x in pnls_mom if x > 0)
        print(f"[H3] momentum (move>=0.12): n={len(pnls_mom)} hit={hit/len(pnls_mom)*100:.0f}% total={tot:+.2f} avg={tot/len(pnls_mom):+.4f}/share")

    # H5: Underdog vs Favourite
    print("\n--- H5: Underdog vs Favourite ---")
    pnls_underdog = []
    pnls_fav = []
    for lc in lcs:
        if len(lc["prices"]) < 1:
            continue
        p = lc["prices"][0]
        if 0.30 <= p < 0.45:
            pnls_underdog.append(pnl_buy("Up", p, lc["winner"]))
        elif 0.55 <= p < 0.70:
            pnls_fav.append(pnl_buy("Up", p, lc["winner"]))

    if pnls_underdog:
        tot = sum(pnls_underdog)
        hit = sum(1 for x in pnls_underdog if x > 0)
        print(f"[H5] underdog 0.30-0.45: n={len(pnls_underdog)} hit={hit/len(pnls_underdog)*100:.0f}% total={tot:+.2f} avg={tot/len(pnls_underdog):+.4f}/share")
    if pnls_fav:
        tot = sum(pnls_fav)
        hit = sum(1 for x in pnls_fav if x > 0)
        print(f"[H5] favourite 0.55-0.70: n={len(pnls_fav)} hit={hit/len(pnls_fav)*100:.0f}% total={tot:+.2f} avg={tot/len(pnls_fav):+.4f}/share")

    # H6: Fade extreme
    print("\n--- H6: Fade Extreme ---")
    pnls_fade = []
    for lc in lcs:
        if len(lc["prices"]) < 2:
            continue
        first = lc["prices"][0]
        if first >= 0.85:
            # Fade: bet Down
            pnls_fade.append(pnl_buy("Down", first, lc["winner"]))
        elif first <= 0.15:
            # Fade: bet Up
            pnls_fade.append(pnl_buy("Up", first, lc["winner"]))
    if pnls_fade:
        tot = sum(pnls_fade)
        hit = sum(1 for x in pnls_fade if x > 0)
        print(f"[H6] fade extreme: n={len(pnls_fade)} hit={hit/len(pnls_fade)*100:.0f}% total={tot:+.2f} avg={tot/len(pnls_fade):+.4f}/share")


if __name__ == "__main__":
    data = load_wallet_data()
    lcs = extract_market_lifecycles(data)
    run_polymarket_battery(lcs)
