# Prediction Market Dashboard Patterns

**Session:** 2026-08-26 — Built Live Dashboard for Prediction Market Lab

---

## Architecture Decisions

### FastAPI Dashboard Pattern

Built a prediction market dashboard with these layers:

```
┌─────────────────────────────────────────┐
│         Dashboard (HTML/JS)             │
│  - Chart.js for price history           │
│  - Auto-refresh every 30s               │
│  - Paper trading UI                     │
└─────────────────┬───────────────────────┘
                  │ REST API
┌─────────────────▼───────────────────────┐
│          FastAPI Server (port 8080)     │
│  - In-memory state                      │
│  - Background scanner task              │
│  - Sample data loader                   │
└─────────────────┬───────────────────────┘
                  │ API calls
┌─────────────────▼───────────────────────┐
│       Data Sources (fallback chain)     │
│  1. Polymarket CLOB (live prices)       │
│  2. Polymarket Gamma (discovery)        │
│  3. Kalshi (alternative venue)          │
│  4. Sample data (historical snapshots)  │
└─────────────────────────────────────────┘
```

### Key Implementation Notes

**Background Scanner Task:**
- Run in asyncio background thread
- Poll CLOB API every 30 seconds
- Update in-memory state with live prices
- Detect opportunities based on strategy rules

**Token ID Mapping Problem:**
- CLOB API requires `token_id` (long hex string)
- Gamma API returns `conditionId` (short hex string)
- These are NOT interchangeable
- Most markets return "No orderbook exists" because they're resolved

**Fallback Pattern:**
```python
async def fetch_live_prices():
    # 1. Try CLOB API for tracked markets
    for cond_id, snap in state.markets.items():
        try:
            url = f"{CLOB}/price?token_id={cond_id}&side=BUY"
            # ... fetch and update price
        except:
            pass  # Market is resolved or no orderbook
    
    # 2. Try Kalshi as fallback
    try:
        kalshi_markets = fetch_kalshi_markets()
        # ... normalize and add to state
    except:
        pass
    
    # 3. Fall back to sample data if nothing live
    if state.scan_count == 0:
        load_sample_data()
```

---

## API Behavior Discovery

### Polymarket CLOB API

**Working Endpoints (no auth):**
- `GET /price?token_id={id}&side=BUY` → `{"price": "0.038"}`
- `GET /midpoint?token_id={id}` → `{"mid": "0.0385"}`
- `GET /book?token_id={id}` → Full order book

**Issues:**
- Most Up/Down markets have `token_id` that returns "No orderbook exists"
- This means markets are **resolved** (price = 0 or 1)
- Active markets with live prices exist but need correct token_id

**Verified Working:**
```bash
curl "https://clob.polymarket.com/price?token_id=107505882767731489358349912513945399560393482969656700824895970500493757150417&side=BUY"
# Returns: {"price":"0.038"}
```

### Polymarket Gamma API

**Endpoints:**
- `GET /public-search?q=BTC+updown` — Search by keyword
- `GET /events?active=true&limit=100` — List events

**Issues:**
- Returns markets with `outcomePrices` as JSON strings (double-encoded)
- Most markets returned are **resolved** (prices = 0 or 1)
- Active markets with live prices are harder to find via search
- Need to iterate `events → markets` two levels deep

**Working Query:**
```bash
curl "https://gamma-api.polymarket.com/events?active=true&limit=100"
# Returns events with nested markets
# Parse outcomePrices with json.loads(market['outcomePrices'])
```

### Kalshi API

**Public Endpoints (no auth):**
- `GET /markets?status=open&limit=100` — Active markets
- `GET /events?limit=50` — Event listing
- `GET /markets/{ticker}/orderbook` — Order book depth

**Response Format:**
- Prices in **cents** (1-99), not dollars
- `yes_bid_dollars`, `yes_ask_dollars` fields
- Volume field name varies (check response)

**Issues:**
- Most markets in sample response had `yes_bid=0.0000`
- May need to filter by `status=open` and check for non-zero bids
- US-regulated markets only (sports, politics, economics)

---

## Strategy Detection Patterns

### H7 (0.5 Discontinuity)
```python
if 0.50 <= price < 0.60:
    edge = 0.066  # Validated from backtest
```

### H2 (Late Favourite)
```python
if price >= 0.70:
    edge = 0.022  # Fade the extreme
```

### H3 (Momentum)
```python
if price_history and len(price_history) >= 2:
    move = abs(price - price_history[-2])
    if move >= 0.12:
        edge = 0.022  # Ride the momentum
```

---

## Dashboard UX Lessons

1. **Status badges must reflect actual state** — Don't show "LIVE" unless real API data is flowing
2. **Auto-refresh with visible feedback** — Show scan count and last scan time
3. **Paper trading modal pattern** — Use simple modals for Enter/Close with size, SL, TP inputs
4. **Chart.js integration** — Add price history charts on demand (click "Chart" button)
5. **Empty states matter** — Show helpful text when no data loaded, not just blank tables

---

## Reference: Full Dashboard Code

The complete implementation is in `scripts/server.py` (~700 lines). Key sections:
- Lines 1-100: Imports and configuration
- Lines 100-300: API endpoints (FastAPI routes)
- Lines 300-500: HTML template with embedded JavaScript
- Lines 500-700: Background scanner task

---

## Next Steps for Production

1. **Build token_id mapping** — Query gamma-api for events, extract clobTokenIds from markets
2. **Add WebSocket support** — Polymarket has `wss://ws-subscriptions-clob.polymarket.com`
3. **Persist state to SQLite** — Currently in-memory only
4. **Add authentication** — For paper trading account persistence
5. **Deploy to Hetzner** — 24/7 operation with cron-based reconnection
