#!/usr/bin/env python3
"""Limitless Exchange API client for live market data."""

import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from typing import Optional


class LimitlessClient:
    """Client for Limitless Exchange API."""
    
    BASE_URL = "https://api.limitless.exchange"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.headers = {"User-Agent": "predictions-lab/0.1"}
        if api_key:
            self.headers["X-API-Key"] = api_key
    
    def get_active_markets(self, limit: int = 25, page: int = 1) -> dict:
        """Get active markets from Limitless."""
        url = f"{self.BASE_URL}/markets/active?page={page}&limit={limit}"
        return self._fetch(url)
    
    def get_market(self, slug: str) -> dict:
        """Get specific market by slug."""
        url = f"{self.BASE_URL}/markets/{slug}"
        return self._fetch(url)
    
    def get_orderbook(self, token_id: str) -> dict:
        """Get orderbook for a token."""
        url = f"{self.BASE_URL}/orderbook/{token_id}"
        return self._fetch(url)
    
    def _fetch(self, url: str) -> dict:
        """Make request to Limitless API."""
        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                return data
        except Exception as e:
            print(f"Limitless API error: {e}", flush=True)
            return {}
    
    def normalize_market(self, market: dict) -> Optional[dict]:
        """Convert Limitless market to standard format."""
        try:
            # Get price from market data
            prices = market.get("prices", [])
            if not prices or len(prices) < 2:
                return None
            
            yes_price = float(prices[0])
            no_price = float(prices[1])
            
            # Filter out resolved markets (price = 0 or 1)
            if yes_price <= 0 or yes_price >= 1:
                return None
            if no_price <= 0 or no_price >= 1:
                return None
            
            return {
                "slug": market.get("slug", ""),
                "question": market.get("title", "")[:60],
                "price": yes_price,
                "volume": float(market.get("volume", 0)),
                "open_interest": float(market.get("openInterest", 0)),
                "trade_type": market.get("tradeType", "unknown"),
                "automation_type": market.get("automationType", "unknown"),
            }
        except Exception as e:
            print(f"Error normalizing market: {e}", flush=True)
            return None


def fetch_limitless_markets() -> list[dict]:
    """Fetch and normalize Limitless markets."""
    client = LimitlessClient()
    all_markets = []
    
    # Pagination (limit is capped at 25)
    for page in range(1, 6):  # Try up to 5 pages
        data = client.get_active_markets(limit=25, page=page)
        markets = data.get("data", [])
        
        if not markets:
            break
        
        for m in markets:
            norm = client.normalize_market(m)
            if norm:
                all_markets.append(norm)
        
        # Check if there are more pages
        total = data.get("totalMarketsCount", 0)
        if page * 25 >= total:
            break
    
    return all_markets


def find_updown_markets(markets: list[dict]) -> list[dict]:
    """Find Up/Down markets in Limitless."""
    updown = []
    for m in markets:
        q = m["question"].lower()
        if "updown" in m["slug"] or ("up" in q and "down" in q):
            updown.append(m)
    return updown


if __name__ == "__main__":
    print("Fetching Limitless markets...")
    markets = fetch_limitless_markets()
    print(f"Found {len(markets)} active markets with prices")
    
    # Find Up/Down markets
    updown = find_updown_markets(markets)
    print(f"Found {len(updown)} potential Up/Down markets")
    
    for m in updown[:5]:
        print(f"  {m['question'][:50]:50} | p={m['price']:.3f} | vol=${m['volume']:,.0f}")
