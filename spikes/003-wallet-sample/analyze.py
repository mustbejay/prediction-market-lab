#!/usr/bin/env python3
"""Collect and summarize public Polymarket wallet trades, read-only."""

from __future__ import annotations

import argparse
import json
import re
import statistics
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

API = "https://data-api.polymarket.com/trades"
USER_AGENT = "PredictionMarketLab/0.1 (read-only wallet research)"


def fetch_page(wallet: str, limit: int, offset: int) -> list[dict[str, Any]]:
    url = API + "?" + urllib.parse.urlencode(
        {"user": wallet, "limit": limit, "offset": offset}
    )
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if not isinstance(payload, list):
        raise TypeError("expected trade list")
    return payload


def trade_key(trade: dict[str, Any]) -> tuple[Any, ...]:
    return (
        trade.get("transactionHash"),
        trade.get("asset"),
        trade.get("timestamp"),
        trade.get("side"),
        trade.get("price"),
        trade.get("size"),
    )


def collect(wallet: str, pages: int, page_size: int) -> list[dict[str, Any]]:
    unique: dict[tuple[Any, ...], dict[str, Any]] = {}
    for page in range(pages):
        rows = fetch_page(wallet, page_size, page * page_size)
        for row in rows:
            unique[trade_key(row)] = row
        if len(rows) < page_size:
            break
        time.sleep(0.1)
    return sorted(unique.values(), key=lambda row: int(row.get("timestamp") or 0))


def summarize_market(rows: list[dict[str, Any]]) -> dict[str, Any]:
    buys = [row for row in rows if str(row.get("side", "")).upper() == "BUY"]
    by_outcome: dict[str, list[dict[str, Any]]] = defaultdict(list)
    switches = 0
    previous: str | None = None
    for row in buys:
        outcome = str(row.get("outcome", "")).strip().lower()
        by_outcome[outcome].append(row)
        if previous is not None and outcome != previous:
            switches += 1
        previous = outcome

    def quantity(outcome: str) -> float:
        return sum(float(row.get("size") or 0) for row in by_outcome[outcome])

    def vwap(outcome: str) -> float | None:
        qty = quantity(outcome)
        if not qty:
            return None
        return sum(
            float(row.get("size") or 0) * float(row.get("price") or 0)
            for row in by_outcome[outcome]
        ) / qty

    up_qty, down_qty = quantity("up"), quantity("down")
    up_vwap, down_vwap = vwap("up"), vwap("down")
    paired = min(up_qty, down_qty)
    largest = max(up_qty, down_qty)
    pair_cost = (
        up_vwap + down_vwap
        if up_vwap is not None and down_vwap is not None
        else None
    )
    title = str(rows[0].get("title") or "")
    slug = str(rows[0].get("slug") or "")
    return {
        "condition_id": rows[0].get("conditionId"),
        "title": title,
        "slug": slug,
        "buy_fills": len(buys),
        "sell_fills": len(rows) - len(buys),
        "up_quantity": up_qty,
        "down_quantity": down_qty,
        "up_vwap": up_vwap,
        "down_vwap": down_vwap,
        "paired_quantity": paired,
        "balance_ratio": paired / largest if largest else 0,
        "pair_cost": pair_cost,
        "locked_pair_pnl_before_fees": paired * (1 - pair_cost) if pair_cost is not None else None,
        "remainder_quantity": abs(up_qty - down_qty),
        "remainder_outcome": "up" if up_qty > down_qty else "down" if down_qty > up_qty else None,
        "outcome_switches": switches,
        "is_up_down": "up or down" in title.lower() or "updown" in slug.lower(),
        "first_timestamp": min(int(row.get("timestamp") or 0) for row in rows),
        "last_timestamp": max(int(row.get("timestamp") or 0) for row in rows),
    }


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def market_window(slug: str) -> tuple[int, int] | None:
    match = re.search(r"-(5m|15m|1h|4h)-(\d+)$", slug)
    if not match:
        return None
    duration = {"5m": 300, "15m": 900, "1h": 3600, "4h": 14400}[match.group(1)]
    start = int(match.group(2))
    return start, start + duration


def aggregate_stats(markets: list[dict[str, Any]]) -> dict[str, Any]:
    two_sided = [
        market
        for market in markets
        if market["up_quantity"] > 0 and market["down_quantity"] > 0
    ]
    pair_costs = [float(market["pair_cost"]) for market in two_sided]
    balances = [float(market["balance_ratio"]) for market in two_sided]
    switches = [float(market["outcome_switches"]) for market in markets]
    return {
        "market_count": len(markets),
        "two_sided_count": len(two_sided),
        "two_sided_share": len(two_sided) / len(markets) if markets else None,
        "median_pair_cost_two_sided": median(pair_costs),
        "pair_cost_below_one_share": (
            sum(cost < 1 for cost in pair_costs) / len(pair_costs) if pair_costs else None
        ),
        "median_balance_ratio_two_sided": median(balances),
        "median_switches": median(switches),
    }


def analyze(wallet: str, trades: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        condition = str(trade.get("conditionId") or "")
        if condition:
            grouped[condition].append(trade)
    markets = [summarize_market(rows) for rows in grouped.values()]
    up_down = [market for market in markets if market["is_up_down"]]
    first_timestamp = (
        min(int(trade.get("timestamp") or 0) for trade in trades) if trades else None
    )
    last_timestamp = (
        max(int(trade.get("timestamp") or 0) for trade in trades) if trades else None
    )
    complete: list[dict[str, Any]] = []
    for market in up_down:
        window = market_window(str(market["slug"]))
        is_complete = bool(
            window
            and first_timestamp is not None
            and last_timestamp is not None
            and first_timestamp <= window[0]
            and last_timestamp >= window[1]
        )
        market["market_window"] = list(window) if window else None
        market["complete_within_sample"] = is_complete
        if is_complete:
            complete.append(market)
    return {
        "wallet": wallet.lower(),
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "trade_rows": len(trades),
        "market_count": len(markets),
        "first_timestamp": first_timestamp,
        "last_timestamp": last_timestamp,
        "all_up_down_stats": aggregate_stats(up_down),
        "complete_up_down_stats": aggregate_stats(complete),
        "markets": sorted(markets, key=lambda market: market["last_timestamp"], reverse=True),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("wallet")
    parser.add_argument("--pages", type=int, default=3)
    parser.add_argument("--page-size", type=int, default=500)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    trades = collect(args.wallet, args.pages, args.page_size)
    report = analyze(args.wallet, trades)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    headline = {key: value for key, value in report.items() if key != "markets"}
    print(json.dumps(headline, indent=2))
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
