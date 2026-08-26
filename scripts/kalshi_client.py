#!/usr/bin/env python3
"""Kalshi API integration for prediction market dashboard."""

import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from typing import Optional


class KalshiClient:
    """Client for Kalshi public market data API."""
    
    BASE_URL = "https://external-api.kalshi.com/trade-api/v2"
    
    def __init__(self):
        self.headers = {"User-Agent": "predictions-lab/0.1"}
    
    def get_markets(self, status: str = "open", limit: int = 100) -> list[dict]:
        """Get active Kalshi markets."""
        url = f"{self.BASE_URL}/markets?status={status}&limit={limit}"
        return self._fetch(url)
    
    def get_events(self, limit: int = 50) -> list[dict]:
        """Get Kalshi events."""
        url = f"{self.BASE_URL}/events?limit={limit}"
        return self._fetch(url)
    
    def get_orderbook(self, ticker: str) -> Optional[dict]:
        """Get orderbook for a specific market."""
        url = f"{self.BASE_URL}/markets/{ticker}/orderbook"
        return self._fetch(url)
    
    def _fetch(self, url: str) -> list[dict]:
        """Make unauthenticated request to Kalshi API."""
        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                return data.get("markets", data.get("events", []))
        except Exception as e:
            print(f"Kalshi API error: {e}", flush=True)
            return []
    
    def normalize_market(self, kalshi_market: dict) -> dict:
        """Convert Kalshi market to standard format."""
        yes_bid = float(kalshi_market.get("yes_bid_dollars", "0"))
        yes_ask = float(kalshi_market.get("yes_ask_dollars", "0"))
        
        # Use mid price
        price = (yes_bid + yes_ask) / 2 if yes_bid > 0 and yes_ask > 0 else yes_bid
        
        return {
            "ticker": kalshi_market.get("ticker", ""),
            "question": kalshi_market.get("title", "")[:60],
            "price": price,
            "yes_bid": yes_bid,
            "yes_ask": yes_ask,
            "volume": float(kalshi_market.get("volume", "0")),
            "open_interest": float(kalshi_market.get("open_interest", "0")),
            "close_time": kalshi_market.get("close_time", ""),
            "market_type": kalshi_market.get("market_type", "binary"),
        }


def fetch_kalshi_markets() -> list[dict]:
    """Fetch and normalize Kalshi markets."""
    client = KalshiClient()
    markets = client.get_markets(status="open", limit=100)
    
    normalized = []
    for m in markets:
        try:
            norm = client.normalize_market(m)
            # Only include markets with realistic prices
            if 0 < norm["price"] < 1 and norm["volume"] > 0:
                normalized.append(norm)
        except Exception as e:
            print(f"Error normalizing market: {e}", flush=True)
    
    return normalized


def find_updown_markets(markets: list[dict]) -> list[dict]:
    """Find Up/Down markets in Kalshi."""
    updown = []
    for m in markets:
        q = m["question"].lower()
        if ("up" in q or "down" in q) and ("price" in q or "hit" in q or "reach" in q):
            updown.append(m)
    return updown


if __name__ == "__main__":
    print("Fetching Kalshi markets...")
    markets = fetch_kalshi_markets()
    print(f"Found {len(markets)} active markets with volume")
    
    # Find Up/Down markets
    updown = find_updown_markets(markets)
    print(f"Found {len(updown)} potential Up/Down markets")
    
    for m in updown[:5]:
        print(f"  {m['question'][:50]:50} | p={m['price']:.3f} | vol=${m['volume']:,.0f}")
