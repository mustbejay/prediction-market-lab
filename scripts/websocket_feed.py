#!/usr/bin/env python3
"""Real-time WebSocket feed for Polymarket Up/Down markets."""

import json
import sys
import time
import asyncio
import websockets
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

POLYMARKET_WS_URL = "wss://ws-gate.polymarket.com/socket.io/?EIO=4&transport=websocket"
SUBSCRIBE_TOPICS = ["condition", "cid"]

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
    # Price history for momentum detection
    price_history: list[float] = field(default_factory=list)
    last_price: float = 0.0


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


# ============================================================================
# WEBSOCKET CLIENT
# ============================================================================

class PolymarketWebSocket:
    """Connect to Polymarket WebSocket and stream market data."""

    def __init__(self, assets: list[str] = None, timeframes: list[str] = None):
        self.assets = assets or ["btc", "eth", "sol", "xrp"]
        self.timeframes = timeframes or ["5m", "15m"]
        self.markets: dict[str, MarketSnapshot] = {}
        self._callbacks: list[Callable] = []
        self._ws = None
        self._running = False

    def on_update(self, callback: Callable[[MarketSnapshot], None]):
        """Register callback for market updates."""
        self._callbacks.append(callback)

    async def _connect(self):
        """Establish WebSocket connection."""
        print(f"Connecting to Polymarket WebSocket...")
        self._ws = await websockets.connect(POLYMARKET_WS_URL, ping_timeout=30)
        print("Connected. Subscribing to markets...")

        # Subscribe to conditions
        for asset in self.assets:
            for tf in self.timeframes:
                query = f"{asset} updown {tf}"
                await self._subscribe_query(query)

    async def _subscribe_query(self, query: str):
        """Subscribe to a market query via WebSocket."""
        # Parse EIO=4 WebSocket protocol
        # Subscribe message format
        subscribe_msg = json.dumps({
            "type": "subscribe",
            "topic": "condition",
            "query": query
        })
        # Socket.IO v4 format: 2[event][payload]
        msg = '2"subscribe"' + subscribe_msg
        await self._ws.send(msg)

    async def _handle_message(self, message: str):
        """Parse and handle incoming WebSocket messages."""
        try:
            # Parse Socket.IO message
            if message.startswith("42"):
                payload = json.loads(message[2:])
                if payload.get("topic") == "condition":
                    data = payload.get("data", {})
                    await self._process_market_data(data)
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
        except Exception as e:
            print(f"Error handling message: {e}")

    async def _process_market_data(self, data: dict):
        """Process market update from WebSocket."""
        condition_id = data.get("conditionId") or data.get("id")
        if not condition_id:
            return

        prices = data.get("prices") or data.get("outcomePrices", [])
        if not prices or len(prices) < 1:
            return

        try:
            p_up = float(prices[0])
        except (TypeError, ValueError):
            return

        # Update or create market snapshot
        if condition_id in self.markets:
            snap = self.markets[condition_id]
            snap.price = p_up
            snap.timestamp = datetime.now(timezone.utc)
            snap.price_history.append(p_up)
            # Keep last 100 prices
            snap.price_history = snap.price_history[-100:]
        else:
            outcome = "Up" if "up" in data.get("slug", "").lower() else "Down"
            snap = MarketSnapshot(
                condition_id=condition_id,
                question=data.get("question", "")[:60],
                outcome=outcome,
                price=p_up,
                timestamp=datetime.now(timezone.utc),
            )
            self.markets[condition_id] = snap

        # Check for opportunities
        opps = self._detect_opportunities(snap)
        if opps:
            print(f"\n[{snap.timestamp.strftime('%H:%M:%S')}] OPPORTUNITY: {snap.question[:40]}...")
            for opp in opps:
                print(f"  → {opp.strategy}: p={snap.price:.3f} expected_edge={opp.expected_edge:+.4f}/share")

        # Notify callbacks
        for cb in self._callbacks:
            try:
                cb(snap, opps)
            except Exception as e:
                print(f"Callback error: {e}")

    def _detect_opportunities(self, snap: MarketSnapshot) -> list[Opportunity]:
        """Detect trading opportunities based on strategy rules."""
        opportunities = []
        p = snap.price

        # H7: 0.5 discontinuity
        if 0.50 <= p < 0.60:
            opportunities.append(Opportunity(
                strategy="H7_high",
                market=snap,
                confidence=0.8,
                entry_price=p,
                expected_edge=0.066,  # from backtest
                reason=f"p(Up)={p:.3f} in [0.5, 0.6) — 0.5 discontinuity"
            ))
        elif 0.40 <= p < 0.50:
            opportunities.append(Opportunity(
                strategy="H7_low",
                market=snap,
                confidence=0.5,
                entry_price=p,
                expected_edge=-0.107,  # negative edge
                reason=f"p(Up)={p:.3f} in [0.4, 0.5) — avoid or fade"
            ))

        # H2: Late favourite (need to check if approaching expiration)
        # This would require TTL data from market metadata

        # H3: Momentum (check price history)
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
                    expected_edge=0.022,  # from backtest
                    reason=f"Momentum {side}: moved {move:+.3f} over {len(snap.price_history)} ticks"
                ))

        return opportunities

    async def run(self):
        """Main WebSocket loop."""
        self._running = True
        try:
            await self._connect()
            while self._running:
                try:
                    message = await asyncio.wait_for(self._ws.recv(), timeout=30)
                    await self._handle_message(message)
                except asyncio.TimeoutError:
                    # Send ping to keep connection alive
                    await self._ws.ping()
                except websockets.exceptions.ConnectionClosed:
                    print("Connection lost. Reconnecting in 5s...")
                    await asyncio.sleep(5)
                    await self._connect()
        except KeyboardInterrupt:
            print("\nStopping WebSocket feed...")
        finally:
            self._running = False
            if self._ws:
                await self._ws.close()


# ============================================================================
# PAPER TRADING ENGINE
# ============================================================================

@dataclass
class PaperPosition:
    """A simulated position."""
    strategy: str
    side: str  # "Up" or "Down"
    entry_price: float
    size: float  # number of shares
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
        """Total account value including unrealized P&L."""
        value = self.balance
        for pos in self.positions:
            # Calculate unrealized P&L
            current_price = pos.market.price
            if pos.side == "Up":
                pnl = (current_price - pos.entry_price) * pos.size
            else:  # Down
                pnl = (pos.entry_price - current_price) * pos.size
            value += pos.size + pnl  # Return of capital + P&L
        return value

    def enter_position(self, opp: Opportunity, size: float = 10.0):
        """Enter a simulated position."""
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
        print(f"  [PAPER] Entered {opp.strategy} {opp.side} @ {opp.entry_price:.3f} x {size} shares")

    def close_position(self, position: PaperPosition, exit_price: float):
        """Close a simulated position."""
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
        """Print account report."""
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
# MAIN ENTRY POINT
# ============================================================================

async def main():
    """Run WebSocket feed with paper trading."""
    import argparse
    parser = argparse.ArgumentParser(description="Polymarket WebSocket Feed + Paper Trading")
    parser.add_argument("--assets", nargs="+", default=["btc", "eth", "sol", "xrp"],
                        help="Assets to track")
    parser.add_argument("--timeframes", nargs="+", default=["5m", "15m"],
                        help="Timeframes to track")
    parser.add_argument("--paper-size", type=float, default=10.0,
                        help="Default position size for paper trading")
    parser.add_argument("--max-positions", type=int, default=5,
                        help="Maximum concurrent positions")
    args = parser.parse_args()

    # Initialize components
    ws = PolymarketWebSocket(assets=args.assets, timeframes=args.timeframes)
    account = PaperAccount()

    # Track open positions by strategy to avoid duplicates
    open_positions: dict[str, PaperPosition] = {}

    def on_market_update(snap: MarketSnapshot, opps: list[Opportunity]):
        """Process market updates and execute paper trades."""
        for opp in opps:
            # Skip if we already have a position for this strategy+market
            key = f"{opp.strategy}:{snap.condition_id}"
            if key in open_positions:
                continue

            # Check if we can enter new position
            if len(open_positions) >= args.max_positions:
                continue

            # Only enter positive-edge strategies
            if opp.expected_edge <= 0:
                continue

            # Enter position
            account.enter_position(opp, args.paper_size)
            open_positions[key] = PaperPosition(
                strategy=opp.strategy,
                side=opp.side,
                entry_price=opp.entry_price,
                size=args.paper_size,
                entry_time=opp.timestamp,
                market=snap,
            )

    ws.on_update(on_market_update)

    print("=" * 60)
    print("POLYMARKET WEBSOCKET FEED + PAPER TRADING")
    print("=" * 60)
    print(f"Assets: {', '.join(args.assets)}")
    print(f"Timeframes: {', '.join(args.timeframes)}")
    print(f"Paper size: {args.paper_size} shares")
    print(f"Max positions: {args.max_positions}")
    print("=" * 60)
    print()

    # Run WebSocket feed
    await ws.run()


if __name__ == "__main__":
    asyncio.run(main())
