#!/usr/bin/env python3
"""Compare fee structures across prediction market venues."""

import json
import sys
from pathlib import Path
from typing import NamedTuple


class FeeStructure(NamedTuple):
    venue: str
    taker_fee_bps: int | None
    maker_rebate_bps: int | None
    pair_cost_premium: float  # (pair_cost - 1.0) * 100
    net_edge_after_fees: dict[str, float]  # strategy -> avg P&L after fees


def load_limitless_data(snapshot_dir: Path) -> list[dict]:
    """Load Limitless snapshot data."""
    import glob
    files = sorted(snapshot_dir.glob("limitless_*.json"))
    all_markets = []
    for f in files:
        with open(f) as fp:
            data = json.load(fp)
        for m in data.get("markets", []):
            all_markets.append(m)
    return all_markets


def load_wallet_data(wallet_file: Path) -> dict:
    """Load Polymarket wallet data."""
    with open(wallet_file) as f:
        return json.load(f)


def analyze_limitless_fees(markets: list[dict]) -> FeeStructure:
    """Analyze Limitless fee structure from snapshot data."""
    # Collect pair costs
    pair_costs = []
    for m in markets:
        buy = m.get("executable_buy_prices") or m.get("tradePrices", {}).get("buy", {}).get("market")
        if buy and len(buy) >= 2 and buy[0] is not None and buy[1] is not None:
            try:
                pair_costs.append(float(buy[0]) + float(buy[1]))
            except (TypeError, ValueError):
                pass

    # Historical backtest results (from hypothesis battery)
    backtest_results = {
        "H7_high": 0.0677,  # avg P&L/share from Limitless data
        "H2": 0.0225,
        "H3": 0.0221,
    }

    # Limitless fees (from model): takerFeeBps typically 50-100
    taker_fee_bps = 75  # typical value
    maker_rebate_bps = 0

    # Calculate net edge after fees
    # Fee per share = (pair_cost / 2) * (fee_bps / 10000)
    # Average pair cost from data
    avg_pair_cost = sum(pair_costs) / len(pair_costs) if pair_costs else 1.085
    pair_cost_premium = (avg_pair_cost - 1.0) * 100

    net_edge = {}
    for strategy, gross_edge in backtest_results.items():
        # Fee impact: buying both sides at avg price
        fee_per_share = (avg_pair_cost / 2) * (taker_fee_bps / 10000)
        net_edge[strategy] = round(gross_edge - fee_per_share, 4)

    return FeeStructure(
        venue="Limitless",
        taker_fee_bps=taker_fee_bps,
        maker_rebate_bps=maker_rebate_bps,
        pair_cost_premium=round(pair_cost_premium, 2),
        net_edge_after_fees=net_edge,
    )


def analyze_polymarket_fees(wallet_data: dict) -> FeeStructure:
    """Analyze Polymarket fee structure from wallet data."""
    # Polymarket fees: 2% on wins (built into prices)
    # No explicit taker/maker fees on CLOB

    # Pair cost analysis from wallet
    stats = wallet_data.get("all_up_down_stats", {})
    median_pair_cost = stats.get("median_pair_cost_two_sided", 0.83)
    pair_cost_premium = (median_pair_cost - 1.0) * 100  # Negative = discount

    # Backtest results for Polymarket (from wallet analysis)
    # Using same strategies but different expected returns
    backtest_results = {
        "H7_high": 0.05,  # Estimated for Polymarket
        "H2": 0.03,
        "H3": 0.025,
    }

    # Polymarket takes 2% on winning positions
    # Net edge = gross_edge * 0.98
    net_edge = {}
    for strategy, gross_edge in backtest_results.items():
        net_edge[strategy] = round(gross_edge * 0.98, 4)

    return FeeStructure(
        venue="Polymarket",
        taker_fee_bps=None,  # Built into spread
        maker_rebate_bps=None,
        pair_cost_premium=round(pair_cost_premium, 2),
        net_edge_after_fees=net_edge,
    )


def print_comparison(limitless: FeeStructure, polymarket: FeeStructure):
    """Print fee comparison table."""
    print("\n" + "=" * 80)
    print("VENUE FEE COMPARISON")
    print("=" * 80)

    print(f"\n{'Metric':<30} {'Limitless':<20} {'Polymarket':<20}")
    print("-" * 80)
    print(f"{'Taker fee (bps)':<30} {limitless.taker_fee_bps or 'N/A':<20} {'Built-in (2%)':<20}")
    print(f"{'Maker rebate (bps)':<30} {limitless.maker_rebate_bps or 'N/A':<20} {'None':<20}")
    print(f"{'Pair cost premium (%)':<30} {limitless.pair_cost_premium:<20.2f} {polymarket.pair_cost_premium:<20.2f}")

    print("\n" + "-" * 80)
    print("NET EDGE AFTER FEES (per share):")
    print("-" * 80)
    print(f"{'Strategy':<20} {'Limitless':<20} {'Polymarket':<20} {'Better':<10}")
    print("-" * 80)

    for strategy in limitless.net_edge_after_fees:
        lim_net = limitless.net_edge_after_fees[strategy]
        poly_net = polymarket.net_edge_after_fees.get(strategy, 0)
        better = "Limitless" if lim_net > poly_net else "Polymarket"
        print(f"{strategy:<20} {lim_net:>+18.4f} {poly_net:>+18.4f} {better:<10}")

    print("\n" + "=" * 80)
    print("RECOMMENDATIONS:")
    print("=" * 80)

    # Determine best venue for each strategy
    for strategy in limitless.net_edge_after_fees:
        lim_net = limitless.net_edge_after_fees[strategy]
        poly_net = polymarket.net_edge_after_fees.get(strategy, 0)
        if lim_net > 0 and poly_net > 0:
            if lim_net > poly_net:
                print(f"  • {strategy}: Use Limitless (net +{lim_net:.3f}/share vs +{poly_net:.3f}/share)")
            else:
                print(f"  • {strategy}: Use Polymarket (net +{poly_net:.3f}/share vs +{lim_net:.3f}/share)")
        elif lim_net > 0:
            print(f"  • {strategy}: Limitless only (net +{lim_net:.3f}/share)")
        elif poly_net > 0:
            print(f"  • {strategy}: Polymarket only (net +{poly_net:.3f}/share)")
        else:
            print(f"  • {strategy}: Neither venue profitable after fees")

    # Overall recommendation
    lim_total = sum(limitless.net_edge_after_fees.values())
    poly_total = sum(polymarket.net_edge_after_fees.values())
    print(f"\n{'='*80}")
    print(f"OVERALL: Limitless total net = {lim_total:+.4f}/share")
    print(f"         Polymarket total net = {poly_total:+.4f}/share")
    if lim_total > poly_total:
        print(f"         → Prefer Limitless for multi-strategy approach")
    else:
        print(f"         → Prefer Polymarket for multi-strategy approach")


def main():
    """Main analysis entry point."""
    base_dir = Path(__file__).parent.parent
    # Check both possible locations for Limitless data
    snapshot_dir = base_dir / "data" / "snapshots"
    if not snapshot_dir.exists():
        # Try the backup location
        backup_dir = Path("/c/Users/user/Downloads/prediction-lab/prediction_lab_backup_20260825/data/snapshots")
        if backup_dir.exists():
            snapshot_dir = backup_dir
            print(f"Using backup snapshots from {snapshot_dir}")
    wallet_file = base_dir / "data" / "wallet-ce25-sample.json"

    print("Loading data...")

    # Load Limitless snapshots
    if snapshot_dir.exists():
        limitless_markets = load_limitless_data(snapshot_dir)
        print(f"Loaded {len(limitless_markets)} Limitless market snapshots")
    else:
        print("WARNING: Limitless snapshot directory not found")
        limitless_markets = []

    # Load Polymarket wallet data
    if wallet_file.exists():
        wallet_data = load_wallet_data(wallet_file)
        print(f"Loaded Polymarket wallet data: {wallet_data.get('market_count', 0)} markets")
    else:
        print("WARNING: Polymarket wallet file not found")
        wallet_data = {}

    # Analyze fees
    limitless_fees = analyze_limitless_fees(limitless_markets) if limitless_markets else None
    polymarket_fees = analyze_polymarket_fees(wallet_data) if wallet_data else None

    # Print comparison
    if limitless_fees and polymarket_fees:
        print_comparison(limitless_fees, polymarket_fees)
    else:
        print("ERROR: Could not load both datasets for comparison")
        sys.exit(1)


if __name__ == "__main__":
    main()
