#!/usr/bin/env python3
"""
Spike 005: Trend Intel Command Center

Wires spikes 001-004 together into a unified view of Up/Down market
opportunities on Polymarket. Discovers markets, reconstructs inventory,
scores opportunities, and detects regime — all without credentials.

Usage:
    python spike.py                        # Default assets (btc, eth, sol, xrp)
    python spike.py --assets btc eth       # Specific assets
    python spike.py --output result.json  # Save to file
    python spike.py --check-kill          # Check kill switch only
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Kill Switch (from spike 004)
# ---------------------------------------------------------------------------

class KillSwitch:
    """File-based emergency halt. No restart required."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or Path("KILL")

    @property
    def is_active(self) -> bool:
        return self._path.exists()

    def activate(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            f"killed_at={datetime.now(timezone.utc).isoformat()}\n",
            encoding="utf-8",
        )

    def deactivate(self) -> None:
        if self._path.exists():
            self._path.unlink()

    def check(self) -> None:
        if self.is_active:
            print(f"ERROR: Kill switch active at {self._path}", file=sys.stderr)
            sys.exit(1)


# ---------------------------------------------------------------------------
# Market Discovery
# ---------------------------------------------------------------------------

API = "https://gamma-api.polymarket.com/public-search"
USER_AGENT = "PredictionMarketLab/0.1 (spike-005 trend intel)"

ASSETS = ("btc", "eth", "sol", "xrp")
UPDOWN_PATTERN = re.compile(
    r"-(?:btc|eth|sol|xrp)-updown-(5m|15m|1h|4h|1d)-(\d{10})$",
    re.IGNORECASE,
)


def decoded(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def fetch(query: str, limit: int) -> dict[str, Any]:
    url = API + "?" + urllib.parse.urlencode(
        {"q": query, "limit_per_type": max(1, min(limit, 50))}
    )
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def discover_updown_markets(
    assets: tuple[str, ...] | None = None,
    limit: int = 20,
    timeframes: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    """Discover active Up/Down markets for configured assets and timeframes."""
    if assets is None:
        assets = ASSETS
    if timeframes is None:
        timeframes = ("5m", "15m")

    markets = []
    seen_condition_ids: set[str] = set()

    for asset in assets:
        for tf in timeframes:
            query = f"{asset} updown {tf}"
            try:
                payload = fetch(query, limit)
                for event in payload.get("events", []):
                    for market in event.get("markets", []):
                        if not market.get("active") or market.get("closed"):
                            continue

                        condition_id = market.get("conditionId", "")
                        if condition_id in seen_condition_ids:
                            continue
                        seen_condition_ids.add(condition_id)

                        slug = str(market.get("slug", "")).lower()
                        match = UPDOWN_PATTERN.search(slug)
                        if not match:
                            continue

                        detected_tf = match.group(1)
                        if detected_tf not in timeframes:
                            continue

                        markets.append({
                            "asset": asset.lower(),
                            "condition_id": condition_id,
                            "market_id": market.get("id"),
                            "slug": slug,
                            "question": market.get("question", ""),
                            "end_date": market.get("endDate"),
                            "outcomes": decoded(market.get("outcomes")) or [],
                            "prices": [number(p) for p in decoded(market.get("outcomePrices")) or []],
                            "best_bid": number(market.get("bestBid")),
                            "best_ask": number(market.get("bestAsk")),
                            "spread": number(market.get("spread")),
                            "liquidity": number(market.get("liquidityNum") or market.get("liquidity")),
                            "volume_24h": number(market.get("volume24hr")),
                            "accepting_orders": bool(market.get("acceptingOrders")),
                            "timeframe": detected_tf,
                            "timestamp_period": int(match.group(2)),
                        })
            except Exception as e:
                print(f"WARNING: Failed to fetch {asset} {tf}: {e}", file=sys.stderr)
                continue

            time.sleep(0.1)

    return markets


# ---------------------------------------------------------------------------
# Inventory Reconstruction
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InventoryMetrics:
    condition_id: str
    asset: str
    slug: str
    up_quantity: float
    down_quantity: float
    up_vwap: float | None
    down_vwap: float | None
    paired_quantity: float
    balance_ratio: float
    pair_cost: float | None
    locked_pair_pnl_before_fees: float | None
    remainder_outcome: str | None
    remainder_quantity: float
    outcome_switches: int
    fill_count: int


def fetch_trade_history(condition_id: str, limit: int = 1000) -> list[dict[str, Any]]:
    """Fetch trade history for a condition ID from Polymarket data API."""
    url = f"https://data-api.polymarket.com/trades?conditionId={condition_id}&limit={limit}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.load(response)
            if isinstance(data, list):
                return data
            return []
    except Exception:
        return []


def reconstruct(
    fills: list[dict[str, Any]],
    condition_id: str,
    asset: str,
    slug: str,
) -> InventoryMetrics:
    """Reconstruct inventory metrics from trade history."""
    ordered = sorted(fills, key=lambda f: int(f.get("timestamp") or 0))
    if not ordered:
        return InventoryMetrics(
            condition_id=condition_id,
            asset=asset,
            slug=slug,
            up_quantity=0.0,
            down_quantity=0.0,
            up_vwap=None,
            down_vwap=None,
            paired_quantity=0.0,
            balance_ratio=0.0,
            pair_cost=None,
            locked_pair_pnl_before_fees=None,
            remainder_outcome=None,
            remainder_quantity=0.0,
            outcome_switches=0,
            fill_count=0,
        )

    quantity = {"up": 0.0, "down": 0.0}
    notional = {"up": 0.0, "down": 0.0}
    switches = 0
    previous: str | None = None

    for fill in ordered:
        outcome = str(fill.get("outcome", "")).strip().lower()
        if outcome not in quantity:
            continue
        try:
            price = float(fill.get("price") or 0)
            size = float(fill.get("size") or 0)
        except (TypeError, ValueError):
            continue

        if not (0 <= price <= 1):
            continue
        if size <= 0:
            continue

        quantity[outcome] += size
        notional[outcome] += size * price
        if previous is not None and outcome != previous:
            switches += 1
        previous = outcome

    up_vwap = notional["up"] / quantity["up"] if quantity["up"] else None
    down_vwap = notional["down"] / quantity["down"] if quantity["down"] else None
    paired = min(quantity.values())
    largest = max(quantity.values())
    balance = paired / largest if largest else 0.0
    pair_cost = up_vwap + down_vwap if up_vwap and down_vwap else None
    locked_pnl = paired * (1 - pair_cost) if pair_cost is not None else None

    if quantity["up"] > quantity["down"]:
        remainder_outcome = "up"
    elif quantity["down"] > quantity["up"]:
        remainder_outcome = "down"
    else:
        remainder_outcome = None

    return InventoryMetrics(
        condition_id=condition_id,
        asset=asset,
        slug=slug,
        up_quantity=quantity["up"],
        down_quantity=quantity["down"],
        up_vwap=up_vwap,
        down_vwap=down_vwap,
        paired_quantity=paired,
        balance_ratio=balance,
        pair_cost=pair_cost,
        locked_pair_pnl_before_fees=locked_pnl,
        remainder_outcome=remainder_outcome,
        remainder_quantity=abs(quantity["up"] - quantity["down"]),
        outcome_switches=switches,
        fill_count=len(ordered),
    )


# ---------------------------------------------------------------------------
# Regime Detection
# ---------------------------------------------------------------------------

def detect_regime(market_data: list[InventoryMetrics]) -> dict[str, Any]:
    """Detect basket-wide regime based on pair cost distribution."""
    pair_costs = [m.pair_cost for m in market_data if m.pair_cost is not None]
    balance_ratios = [m.balance_ratio for m in market_data if m.balance_ratio > 0]

    if not pair_costs:
        return {
            "classification": "unknown",
            "median_pair_cost": None,
            "median_balance_ratio": None,
            "market_count": len(market_data),
            "markets_with_data": 0,
        }

    sorted_costs = sorted(pair_costs)
    sorted_balances = sorted(balance_ratios)

    median_cost = sorted_costs[len(sorted_costs) // 2]
    median_balance = sorted_balances[len(sorted_balances) // 2] if sorted_balances else 0.0

    if median_cost < 0.90:
        classification = "trending_strong"
    elif median_cost < 0.95:
        classification = "trending"
    elif median_cost < 1.00:
        classification = "balanced"
    else:
        classification = "chop"

    return {
        "classification": classification,
        "median_pair_cost": round(median_cost, 4),
        "median_balance_ratio": round(median_balance, 4),
        "market_count": len(market_data),
        "markets_with_data": len(pair_costs),
        "pair_cost_below_0.95": sum(1 for c in pair_costs if c < 0.95),
        "pair_cost_below_0.90": sum(1 for c in pair_costs if c < 0.90),
    }


# ---------------------------------------------------------------------------
# Opportunity Scoring
# ---------------------------------------------------------------------------

def score_market(metrics: InventoryMetrics, regime: dict[str, Any]) -> dict[str, Any]:
    """Score a market based on opportunity criteria."""
    if not metrics.pair_cost or metrics.fill_count == 0:
        return {
            "score": 0.0,
            "opportunity": "none",
            "recommendation": "avoid",
            "reason": "no trade data",
        }

    # Normalize metrics
    pair_cost_score = max(0, min(1, (1 - (metrics.pair_cost - 0.80) / 0.20)))
    balance_score = min(1, metrics.balance_ratio / 0.8)
    switch_score = min(1, metrics.outcome_switches / 5)
    volume_score = 1.0 if metrics.up_quantity + metrics.down_quantity > 10 else 0.5

    # Composite
    weights = {"pair_cost": 0.4, "balance": 0.3, "switches": 0.2, "volume": 0.1}
    composite = (
        pair_cost_score * weights["pair_cost"]
        + balance_score * weights["balance"]
        + switch_score * weights["switches"]
        + volume_score * weights["volume"]
    )

    if composite >= 0.7:
        opportunity, recommendation = "high", "watch"
    elif composite >= 0.4:
        opportunity, recommendation = "medium", "consider"
    else:
        opportunity, recommendation = "low", "avoid"

    return {
        "score": round(composite, 4),
        "opportunity": opportunity,
        "recommendation": recommendation,
        "pair_cost_score": round(pair_cost_score, 4),
        "balance_score": round(balance_score, 4),
        "switch_score": round(switch_score, 4),
        "volume_score": round(volume_score, 4),
        "reason": f"pair_cost={metrics.pair_cost:.4f}, balance={metrics.balance_ratio:.2f}, switches={metrics.outcome_switches}",
    }


# ---------------------------------------------------------------------------
# Audit Trail
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScanRecord:
    generated_at: str
    regime_classification: str
    market_count: int
    markets_with_data: int
    median_pair_cost: float | None
    top_opportunity_count: int


class AuditTrail:
    def __init__(self, log_path: Path | None = None) -> None:
        self._log_path = log_path or Path("scan-history.jsonl")

    def log(self, record: ScanRecord) -> None:
        line = json.dumps(asdict(record), default=str, separators=(",", ":"))
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")


# ---------------------------------------------------------------------------
# Main Command Center
# ---------------------------------------------------------------------------

def run_command_center(
    assets: tuple[str, ...] | None = None,
    limit: int = 20,
    kill_path: Path | None = None,
    output_path: Path | None = None,
    simulation: bool = True,
    timeframes: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Run the trend intel command center."""
    # Check kill switch
    kill = KillSwitch(kill_path)
    kill.check()

    audit = AuditTrail()

    # Phase 1: Market Discovery
    print(f"Discovering Up/Down markets for {assets or ASSETS}...")
    markets = discover_updown_markets(assets, limit, timeframes)
    print(f"  Found {len(markets)} active Up/Down markets")

    # Phase 2: Inventory Reconstruction
    print("Reconstructing inventory...")
    enriched_markets = []
    for market in markets:
        condition_id = market["condition_id"]
        fills = fetch_trade_history(condition_id)
        if not fills:
            enriched_markets.append({**market, "inventory": None, "score": None})
            continue

        metrics = reconstruct(fills, condition_id, market["asset"], market["slug"])
        enriched_markets.append({**market, "inventory": asdict(metrics), "score": None})

    # Phase 3: Regime Detection
    markets_with_data = [m for m in enriched_markets if m.get("inventory")]
    regime = detect_regime([InventoryMetrics(**m["inventory"]) for m in markets_with_data])
    print(f"  Regime: {regime['classification']} (median pair cost: {regime.get('median_pair_cost')})")

    # Phase 4: Opportunity Scoring
    print("Scoring opportunities...")
    for market in enriched_markets:
        if market.get("inventory"):
            score = score_market(
                InventoryMetrics(**market["inventory"]),
                regime,
            )
            market["score"] = score

    # Build result
    scored = [m for m in enriched_markets if m.get("score")]
    scored.sort(key=lambda m: m["score"]["score"], reverse=True)

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "regime": regime,
        "markets": enriched_markets,
        "top_opportunities": scored[:10],
        "summary": {
            "total_markets": len(enriched_markets),
            "markets_with_data": len(markets_with_data),
            "high_opportunities": sum(1 for m in scored if m["score"]["opportunity"] == "high"),
            "medium_opportunities": sum(1 for m in scored if m["score"]["opportunity"] == "medium"),
            "low_opportunities": sum(1 for m in scored if m["score"]["opportunity"] == "low"),
        },
    }

    # Audit
    audit.log(ScanRecord(
        generated_at=result["generated_at"],
        regime_classification=regime["classification"],
        market_count=len(enriched_markets),
        markets_with_data=len(markets_with_data),
        median_pair_cost=regime.get("median_pair_cost"),
        top_opportunity_count=result["summary"]["high_opportunities"],
    ))

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"Output written to {output_path}")

    return result


def print_summary(result: dict[str, Any]) -> None:
    print("\n" + "=" * 60)
    print("TREND INTEL COMMAND CENTER")
    print("=" * 60)
    print(f"Generated: {result['generated_at']}")
    print(f"Regime: {result['regime']['classification']}")
    print(f"Markets found: {result['summary']['total_markets']}")
    print(f"Markets with data: {result['summary']['markets_with_data']}")
    print(f"\nOpportunities:")
    print(f"  High: {result['summary']['high_opportunities']}")
    print(f"  Medium: {result['summary']['medium_opportunities']}")
    print(f"  Low: {result['summary']['low_opportunities']}")

    if result.get("top_opportunities"):
        print(f"\nTop Opportunities:")
        for i, m in enumerate(result["top_opportunities"][:5], 1):
            inv = m.get("inventory")
            score = m.get("score", {})
            if inv:
                print(f"  {i}. {m['asset'].upper()} {inv['condition_id'][:16]}...")
                print(f"     Pair Cost: {inv.get('pair_cost', 'N/A')}")
                print(f"     Balance: {inv.get('balance_ratio', 0):.2f}")
                print(f"     Score: {score.get('score', 0):.2f} ({score.get('recommendation', 'N/A')})")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Trend Intel Command Center - Up/Down Market Scanner"
    )
    parser.add_argument(
        "--assets",
        nargs="+",
        choices=ASSETS,
        default=None,
        help=f"Assets to scan (default: {', '.join(ASSETS)})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Max markets per asset (default: 20)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON file path",
    )
    parser.add_argument(
        "--kill-path",
        type=Path,
        default=None,
        help="Custom kill switch file path",
    )
    parser.add_argument(
        "--check-kill",
        action="store_true",
        help="Only check kill switch and exit",
    )
    parser.add_argument(
        "--simulation",
        action="store_true",
        default=True,
        help="Simulation mode (default)",
    )

    args = parser.parse_args()

    if args.check_kill:
        kill = KillSwitch(args.kill_path)
        if kill.is_active:
            print(f"Kill switch is ACTIVE at {kill._path}")
            sys.exit(1)
        else:
            print(f"Kill switch is INACTIVE at {kill._path}")
            sys.exit(0)

    result = run_command_center(
        assets=tuple(args.assets) if args.assets else None,
        limit=args.limit,
        kill_path=args.kill_path,
        output_path=args.output,
        simulation=args.simulation,
        timeframes=("5m", "15m"),
    )

    print_summary(result)


if __name__ == "__main__":
    main()
