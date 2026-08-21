#!/usr/bin/env python3
"""Read-only Polymarket Gamma search and normalized snapshot CLI."""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

API = "https://gamma-api.polymarket.com/public-search"
USER_AGENT = "PredictionMarketLab/0.1 (read-only research)"


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


def normalize(payload: dict[str, Any], query: str) -> dict[str, Any]:
    markets: list[dict[str, Any]] = []
    for event in payload.get("events", []):
        for market in event.get("markets", []):
            if not market.get("active") or market.get("closed"):
                continue
            outcomes = decoded(market.get("outcomes")) or []
            prices = decoded(market.get("outcomePrices")) or []
            markets.append(
                {
                    "event_id": event.get("id"),
                    "event": event.get("title"),
                    "market_id": market.get("id"),
                    "question": market.get("question"),
                    "end_date": market.get("endDate"),
                    "accepting_orders": bool(market.get("acceptingOrders")),
                    "restricted": bool(market.get("restricted") or event.get("restricted")),
                    "outcomes": outcomes,
                    "prices": [number(p) for p in prices],
                    "best_bid": number(market.get("bestBid")),
                    "best_ask": number(market.get("bestAsk")),
                    "spread": number(market.get("spread")),
                    "liquidity": number(market.get("liquidityNum") or market.get("liquidity")),
                    "volume_24h": number(market.get("volume24hr")),
                    "fees_enabled": bool(market.get("feesEnabled")),
                    "resolution_source": market.get("resolvedBy"),
                    "slug": market.get("slug"),
                }
            )
    markets.sort(key=lambda row: (row["volume_24h"], row["liquidity"]), reverse=True)
    return {
        "source": API,
        "query": query,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "market_count": len(markets),
        "markets": markets,
    }


def print_table(snapshot: dict[str, Any], rows: int) -> None:
    print(f"query={snapshot['query']!r} active_markets={snapshot['market_count']}")
    print("VOL24H      LIQUIDITY   BID    ASK    RESTRICTED  QUESTION")
    for market in snapshot["markets"][:rows]:
        print(
            f"{market['volume_24h']:>10,.0f}  {market['liquidity']:>10,.0f}  "
            f"{market['best_bid']:>5.3f}  {market['best_ask']:>5.3f}  "
            f"{str(market['restricted']):>10}  {market['question']}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query", help="Search term, e.g. Bitcoin or temperature")
    parser.add_argument("--limit", type=int, default=10, help="Events requested")
    parser.add_argument("--rows", type=int, default=12, help="Rows printed")
    parser.add_argument("--output", type=Path, help="Optional normalized JSON snapshot")
    args = parser.parse_args()

    snapshot = normalize(fetch(args.query, args.limit), args.query)
    print_table(snapshot, args.rows)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
        print(f"snapshot={args.output}")


if __name__ == "__main__":
    main()
