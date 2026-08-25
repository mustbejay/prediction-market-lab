#!/usr/bin/env python3
"""Real-time market scanner using REST API polling (WebSocket fallback)."""

import json
import sys
import time
import asyncio
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Optional


# ============================================================================
# CONFIGURATION
# ============================================================================

POLYMARKET_GAMMA = "https://gamma-api.polymarket.com/public-search"
UA = "predictions-lab/0.1 (+scanner)"

# Strategy thresholds
STRATEGY_CONFIG = {
    "H7_high": {"p_range": (0.50, 0.60), "side": "Up", "weight": 0.4},
    "H7_low": {"p_range": (0.40, 0.50), "side": "Up", "weight": 0.3},
    "H2": {"threshold": 0.70, "lookback": 3, "weight": 0.3},
}


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class MarketSnapshot:
    """Current state of a single market."""
    condition_id: str
    question: str
    outcome: str  # "Up" or "Down"
    price: float  # current probability of Up
    timestamp: datetime
    price_history: list[float] = field(default_factory=list)


@dataclass
class Opportunity:
    """Detected trading opportunity."""
    strategy: str
    market: MarketSnapshot
    confidence: float
    entry_price: float
    expected_edge: float
    reason: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PaperPosition:
    """A simulated position."""
    strategy: str
    side: str
    entry_price: float
    size: float
    entry_time: datetime
    market: MarketSnapshot


@dataclass
class PaperAccount:
    """Simulated trading account."""
    balance: float = 10000.0
    positions: list[PaperPosition] = field(default_factory=list)
    trades: list[dict] = field(default_factory=list)
    pnl_history: list[float] = field(default_factory=list)

    @property
    def total_value(self) -> float:
        value = self.balance
        for pos in self.positions:
            current_price = pos.market.price
            if pos.side == "Up":
                pnl = (current_price - pos.entry_price) * pos.size
            else:
                pnl = (pos.entry_price - current_price) * pos.size
            value += pos.size + pnl
        return value

    def enter_position(self, opp: Opportunity, size: float = 10.0):
        position = PaperPosition(
            strategy=opp.strategy,
            side=opp.side,
            entry_price=opp.entry_price,
            size=size,
            entry_time=opp.timestamp,
            market=opp.market,
        )
        self.positions.append(position)
        self.trades.append({
            "action": "BUY",
            "strategy": opp.strategy,
            "price": opp.entry_price,
            "size": size,
            "timestamp": opp.timestamp.isoformat(),
        })
        print(f"  [PAPER] Entered {opp.strategy} {opp.side} @ {opp.entry_price:.3f} x {size}")

    def close_position(self, position: PaperPosition, exit_price: float):
        if position.side == "Up":
            pnl = (exit_price - position.entry_price) * position.size
        else:
            pnl = (position.entry_price - exit_price) * position.size
        self.balance += position.size + pnl
        self.positions.remove(position)
        self.pnl_history.append(pnl)
        self.trades.append({
            "action": "SELL",
            "strategy": position.strategy,
            "price": exit_price,
            "size": position.size,
            "pnl": pnl,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return pnl

    def report(self):
        print(f"\n{'='*60}")
        print(f"PAPER TRADING REPORT")
        print(f"{'='*60}")
        print(f"Balance: ${self.balance:,.2f}")
        print(f"Total Value: ${self.total_value:,.2f}")
        print(f"Open Positions: {len(self.positions)}")
        if self.pnl_history:
            total_pnl = sum(self.pnl_history)
            win_rate = sum(1 for p in self.pnl_history if p > 0) / len(self.pnl_history) * 100
            avg_pnl = total_pnl / len(self.pnl_history)
            print(f"Closed Trades: {len(self.pnl_history)}")
            print(f"Total P&L: ${total_pnl:+,.2f}")
            print(f"Win Rate: {win_rate:.1f}%")
            print(f"Avg P&L/Trade: ${avg_pnl:+.4f}")
        print(f"{'='*60}\n")


# ============================================================================
# POLLING SCANNER
# ============================================================================

class PolymarketScanner:
    """Poll Polymarket API for market updates."""

    def __init__(self, assets: list[str] = None, timeframes: list[str] = None):
        self.assets = assets or ["btc", "eth", "sol", "xrp"]
        self.timeframes = timeframes or ["5m", "15m"]
        self.markets: dict[str, MarketSnapshot] = {}
        self._callbacks: list[Callable] = []
        self._running = False
        self._poll_interval = 30  # seconds
        self._seen_opps: set[str] = set()  # avoid duplicate signals

    def on_update(self, callback: Callable):
        self._callbacks.append(callback)

    def fetch_markets(self, query: str, limit: int = 20) -> list[dict]:
        url = f"{POLYMARKET_GAMMA}?q={urllib.parse.quote(query)}&limit_per_type={limit}"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
                return data.get("events", [])
        except Exception as e:
            print(f"API error: {e}", file=sys.stderr)
            return []

    def analyze_market(self, market: dict) -> MarketSnapshot | None:
        """Analyze a single market."""
        condition_id = market.get("conditionId", "")
        if not condition_id:
            return None

        prices = market.get("outcomePrices", []) or market.get("prices", [])
        if not prices or len(prices) < 1:
            return None

        try:
            p_up = float(prices[0])
        except (TypeError, ValueError):
            return None

        slug = market.get("slug", "").lower()
        outcome = "Up" if "up" in slug else "Down"

        # Check if we already have this market
        if condition_id in self.markets:
            snap = self.markets[condition_id]
            snap.price = p_up
            snap.timestamp = datetime.now(timezone.utc)
            snap.price_history.append(p_up)
            snap.price_history = snap.price_history[-100:]
            return snap
        else:
            snap = MarketSnapshot(
                condition_id=condition_id,
                question=market.get("question", "")[:60],
                outcome=outcome,
                price=p_up,
                timestamp=datetime.now(timezone.utc),
            )
            self.markets[condition_id] = snap
            return snap

    def detect_opportunities(self, snap: MarketSnapshot) -> list[Opportunity]:
        """Detect trading opportunities."""
        opportunities = []
        p = snap.price

        # H7: 0.5 discontinuity
        if 0.50 <= p < 0.60:
            opportunities.append(Opportunity(
                strategy="H7_high",
                market=snap,
                confidence=0.8,
                entry_price=p,
                expected_edge=0.066,
                reason=f"p(Up)={p:.3f} in [0.5, 0.6)"
            ))
        elif 0.40 <= p < 0.50:
            opportunities.append(Opportunity(
                strategy="H7_low",
                market=snap,
                confidence=0.5,
                entry_price=p,
                expected_edge=-0.107,
                reason=f"p(Up)={p:.3f} in [0.4, 0.5)"
            ))

        # H3: Momentum
        if len(snap.price_history) >= 4:
            p0 = snap.price_history[0]
            p_current = snap.price_history[-1]
            move = p_current - p0
            if abs(move) >= 0.12:
                side = "Up" if move > 0 else "Down"
                opportunities.append(Opportunity(
                    strategy="H3_momentum",
                    market=snap,
                    confidence=0.7,
                    entry_price=p_current,
                    expected_edge=0.022,
                    reason=f"Momentum {side}: moved {move:+.3f}"
                ))

        return opportunities

    async def run(self, poll_interval: int = None, max_runs: int = None):
        """Main polling loop."""
        self._running = True
        poll_interval = poll_interval or self._poll_interval
        run_count = 0

        queries = [f"{a} updown {tf}" for a in self.assets for tf in self.timeframes]

        print("=" * 60)
        print("POLYMARKET SCANNER (REST API)")
        print("=" * 60)
        print(f"Assets: {', '.join(self.assets)}")
        print(f"Timeframes: {', '.join(self.timeframes)}")
        print(f"Poll interval: {poll_interval}s")
        print(f"Strategies: H7 (0.5 discontinuity), H3 (momentum)")
        print("=" * 60)
        print()

        try:
            while self._running:
                run_count += 1
                if max_runs and run_count > max_runs:
                    break

                now = datetime.now(timezone.utc)
                print(f"[{now.strftime('%H:%M:%S')}] Poll #{run_count}...", end=" ", flush=True)

                new_opps = []
                for query in queries:
                    events = self.fetch_markets(query, limit=20)
                    for event in events:
                        for market in event.get("markets", []):
                            snap = self.analyze_market(market)
                            if not snap:
                                continue
                            opps = self.detect_opportunities(snap)
                            for opp in opps:
                                key = f"{opp.strategy}:{snap.condition_id}:{opp.timestamp.date()}"
                                if key not in self._seen_opps:
                                    self._seen_opps.add(key)
                                    new_opps.append(opp)

                if new_opps:
                    print(f"Found {len(new_opps)} opportunities!")
                    for opp in new_opps[:5]:
                        print(f"  → {opp.strategy}: {opp.market.question[:40]}... p={opp.entry_price:.3f} edge={opp.expected_edge:+.4f}")
                        for cb in self._callbacks:
                            try:
                                cb(opp)
                            except Exception as e:
                                print(f"    Callback error: {e}")
                else:
                    print(f"No new opportunities ({len(self.markets)} markets tracked)")

                if not max_runs or run_count < max_runs:
                    await asyncio.sleep(poll_interval)

        except KeyboardInterrupt:
            print("\nStopping scanner...")
        finally:
            self._running = False


# ============================================================================
# PAPER TRADING INTEGRATION
# ============================================================================

def create_paper_trader(account: PaperAccount, paper_size: float = 10.0, max_positions: int = 5):
    """Create a callback for paper trading."""
    open_positions: dict[str, PaperPosition] = {}

    def on_opportunity(opp: Opportunity):
        if opp.expected_edge <= 0:
            return
        if len(open_positions) >= max_positions:
            return

        key = f"{opp.strategy}:{opp.market.condition_id}"
        if key in open_positions:
            return

        account.enter_position(opp, paper_size)
        open_positions[key] = PaperPosition(
            strategy=opp.strategy,
            side=opp.side,
            entry_price=opp.entry_price,
            size=paper_size,
            entry_time=opp.timestamp,
            market=opp.market,
        )

    return on_opportunity


# ============================================================================
# MAIN
# ============================================================================

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Polymarket Scanner + Paper Trading")
    parser.add_argument("--assets", nargs="+", default=["btc", "eth", "sol", "xrp"])
    parser.add_argument("--timeframes", nargs="+", default=["5m", "15m"])
    parser.add_argument("--interval", type=int, default=30, help="Poll interval (seconds)")
    parser.add_argument("--runs", type=int, default=None, help="Max runs (None=continuous)")
    parser.add_argument("--paper-size", type=float, default=5.0, help="Position size")
    parser.add_argument("--max-positions", type=int, default=3, help="Max concurrent positions")
    parser.add_argument("--report", action="store_true", help="Print report at end")
    args = parser.parse_args()

    scanner = PolymarketScanner(assets=args.assets, timeframes=args.timeframes)
    account = PaperAccount()
    scanner.on_update(create_paper_trader(account, args.paper_size, args.max_positions))

    await scanner.run(poll_interval=args.interval, max_runs=args.runs)

    if args.report:
        account.report()


if __name__ == "__main__":
    asyncio.run(main())
