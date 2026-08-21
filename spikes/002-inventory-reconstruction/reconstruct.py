#!/usr/bin/env python3
"""Reconstruct two-outcome BUY inventory from chronological fills."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Fill:
    market_id: str
    timestamp: str
    outcome: str
    price: float
    size: float


@dataclass(frozen=True)
class InventoryMetrics:
    market_id: str
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


def _vwap(notional: float, quantity: float) -> float | None:
    return notional / quantity if quantity else None


def reconstruct(fills: Iterable[Fill]) -> InventoryMetrics:
    ordered = sorted(fills, key=lambda fill: fill.timestamp)
    if not ordered:
        raise ValueError("at least one fill is required")
    market_ids = {fill.market_id for fill in ordered}
    if len(market_ids) != 1:
        raise ValueError("all fills must belong to one market")

    quantity = {"up": 0.0, "down": 0.0}
    notional = {"up": 0.0, "down": 0.0}
    switches = 0
    previous: str | None = None

    for fill in ordered:
        outcome = fill.outcome.strip().lower()
        if outcome not in quantity:
            raise ValueError(f"unsupported outcome: {fill.outcome!r}")
        if not 0 <= fill.price <= 1:
            raise ValueError(f"price outside [0, 1]: {fill.price}")
        if fill.size <= 0:
            raise ValueError(f"size must be positive: {fill.size}")
        quantity[outcome] += fill.size
        notional[outcome] += fill.size * fill.price
        if previous is not None and outcome != previous:
            switches += 1
        previous = outcome

    up_vwap = _vwap(notional["up"], quantity["up"])
    down_vwap = _vwap(notional["down"], quantity["down"])
    paired = min(quantity.values())
    largest = max(quantity.values())
    balance = paired / largest if largest else 0.0
    pair_cost = up_vwap + down_vwap if up_vwap is not None and down_vwap is not None else None
    locked_pnl = paired * (1 - pair_cost) if pair_cost is not None else None

    if quantity["up"] > quantity["down"]:
        remainder_outcome = "up"
    elif quantity["down"] > quantity["up"]:
        remainder_outcome = "down"
    else:
        remainder_outcome = None

    return InventoryMetrics(
        market_id=next(iter(market_ids)),
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


def read_csv(path: Path) -> list[Fill]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [
            Fill(
                market_id=row["market_id"],
                timestamp=row["timestamp"],
                outcome=row["outcome"],
                price=float(row["price"]),
                size=float(row["size"]),
            )
            for row in csv.DictReader(handle)
        ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_file", type=Path)
    args = parser.parse_args()
    fills = read_csv(args.csv_file)
    by_market: dict[str, list[Fill]] = {}
    for fill in fills:
        by_market.setdefault(fill.market_id, []).append(fill)
    result = [asdict(reconstruct(group)) for group in by_market.values()]
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
