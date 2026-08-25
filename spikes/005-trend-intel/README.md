---
type: spike-spec
status: planned
created: 2026-08-24
priority: medium
domain: prediction-market
tags: [spike, polymarket, trend-intel, command-center, dump-hedge, inventory-structure]
managed_by: Hermes A8
related_spikes:
  - "001-public-market-data"
  - "002-inventory-reconstruction"
  - "003-wallet-sample"
  - "004-safety-patterns"
sources:
  - "https://medium.com/@Teraus/polymarket-15-minute-dump-and-hedge-bot-89018d7aa8fb"
  - "https://medium.com/@Teraus/unlocking-the-power-of-automated-trading-introducing-my-raydium-volume-bot-for-solana-7c255546f0c7"
  - "C:/Users/user/prediction-market-lab/bot-research.txt"
  - "https://github.com/alsk1992/CloddsBot"
---

# Spike 005: Trend Intel Command Center

## Goal

Build a lightweight CLI + structured JSON output that wires spikes 001–004 together into a unified view of 15m Up/Down market opportunities. The command center discovers markets, reconstructs inventory, scores opportunities, and detects regime — all without credentials or live execution.

## What we're solving

The five top Polymarket bots (from bot-research.txt analysis) share a pattern: their edge isn't in a single signal, it's in **inventory structure** — pair cost, balance ratio, directional remainder, and regime awareness. The dump-and-hedge bot is one simple implementation of this. The command center makes the structure visible across all configured assets.

## Sources

### Polymarket 15m Dump-and-Hedge Bot (Teraus)

- Trades 15m Up/Down binary markets (BTC, ETH, SOL, XRP)
- Strategy: buy side that dumped, hedge when pair cost < target
- Modes: simulation (no real orders), production, redeem-only
- Stop-loss: if hedge never arrives before 5min remaining, sell position or buy opposite anyway
- Uses Polymarket CLOB + Gamma APIs
- Config: `config.json` with gamma_api_url, clob_api_url, api_key, private_key

### Bot Research (bot-research.txt)

Analysis of 1M+ executions from top 5 Polymarket bots:

| Bot | Pattern | Key insight |
|-----|---------|-------------|
| 0xcE25E214… | Dynamic two-sided rotation | Doesn't require cheap pair in every market; allows temporary expensive inventory |
| 0xAAAAA | Fixed-lot directional | 120-contract blocks, median pair cost $1.06 (often above $1) |
| x-MoneyForWhiskas | Balanced micro-fill accumulation | Pair cost ~$0.99, switches ~10x per market |
| bosona | Multi-timeframe regime switching | 5m: cheap pairs ($0.80), 1h+: directional ($1.00+) |
| mo-money | Directional core + hedge overlay | 58% smaller side, hedge reduces exposure but doesn't eliminate directionality |

Common patterns:
1. Up/Down are two parts of the same inventory
2. They trade the price path, not a single snapshot
3. Sizing is part of the algorithm, not just risk control

### CloddsBot (Reference Architecture)

CloddsBot is a comprehensive AI trading terminal (739 stars, MIT license) built for prediction markets and crypto. Key architectural patterns worth borrowing:

**Four-module trading system:**
- `ExecutionService`: orders, fills, tracking
- `BotManager`: strategies, signals, execution
- `SafetyManager`: breakers, drawdown limits, kill switch
- `OpportunityFinder`: arbitrage, matching, scoring

**Risk engine features:**
- Circuit breakers: daily loss ($500), max drawdown (20%), position limit (25%), correlation (3)
- Dynamic Kelly criterion sizing (adaptive based on performance, drawdown, volatility)
- VaR/CVaR calculation
- Volatility regime detection with size multipliers
- Stress testing (5 predefined scenarios)
- SQLite-backed safety state (persisted across restarts)

**Key patterns for our spike:**
1. **Trade Logger** — auto-captures all trades to SQLite, queryable via `/trades stats` and `/trades recent`
2. **Opportunity Finder** — cross-platform arbitrage with semantic entity matching (canonical IDs like `polymarket:trump-2024-president → canonical:election:trump:2024`)
3. **Orderbook Imbalance Detector** — calculates `imbalanceScore`, `bidAskRatio`, `signal`, `confidence` for entry timing
4. **Kill Switch** — immediate halt of all bots, blocks new trades, persisted to SQLite
5. **A/B Testing** — run same strategy on multiple accounts to test variations

**Why this matters:** CloddsBot demonstrates that a well-structured trading system needs four separate concerns (execution, bot management, safety, opportunity finding) with clear interfaces between them. Our spike should adopt this modularity rather than building a monolithic script.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Trend Intel Command Center                │
├─────────────────────────────────────────────────────────────┤
│  CLI Entry (spike.py)                                       │
│       │                                                     │
│       ├─→ Market Discovery (spike 001 logic)                │
│       │     • Poll Gamma API for active 15m markets         │
│       │     • Filter by asset (BTC, ETH, SOL, XRP)          │
│       │     • Return normalized VenueMarket list            │
│       │                                                     │
│       ├─→ Inventory Reconstruction (spike 002 logic)        │
│       │     • Fetch trade history for each market           │
│       │     • Compute: up_qty, down_qty, pair_cost,         │
│       │       balance_ratio, outcome_switches               │
│       │     • Group by condition_id                         │
│       │                                                     │
│       ├─→ Regime Detection (new)                            │
│       │     • Calculate ADX median across basket            │
│       │     • Classify: trending_up, trending_down, chop    │
│       │     • Borrow from AutoAgent regime selector logic   │
│       │                                                     │
│       ├─→ Opportunity Scoring (new)                         │
│       │     • Score each market on:                         │
│       │       - pair_cost < 0.95 (dump-hedge viable)        │
│       │       - balance_ratio > 0.8 (balanced)              │
│       │       - outcome_switches > 5 (active trading)       │
│       │     • Rank by composite score                       │
│       │                                                     │
│       └─→ Safety & Audit (spike 004 logic)                  │
│             • Kill switch check (file-based halt)           │
│             • JSONL audit log (scan records)                │
│             • SQLite query interface                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                      Structured JSON Output
                      (spike-output.json)
```

**Modular design inspired by CloddsBot's four-module architecture:**

| Module | Responsibility | Our spike equivalent |
|--------|----------------|----------------------|
| ExecutionService | orders, fills, tracking | Not yet (read-only for now) |
| BotManager | strategies, signals, execution | OpportunityScorer |
| SafetyManager | breakers, drawdown, kill switch | KillSwitch + AuditTrail |
| OpportunityFinder | arbitrage, matching, scoring | RegimeDetector + OpportunityScorer |

## Output Schema

```json
{
  "generated_at": "2026-08-24T10:00:00Z",
  "regime": {
    "classification": "chop",
    "adx_median": 15.2,
    "basket_trending_count": 2,
    "basket_total": 4
  },
  "markets": [
    {
      "asset": "btc",
      "condition_id": "0x...",
      "slug": "btc-updown-15m-1234567890",
      "pair_cost": 0.92,
      "balance_ratio": 0.85,
      "outcome_switches": 12,
      "up_quantity": 150.0,
      "down_quantity": 127.5,
      "up_vwap": 0.48,
      "down_vwap": 0.44,
      "score": 0.78,
      "opportunity": "high"
    }
  ],
  "top_opportunities": [
    {
      "rank": 1,
      "condition_id": "0x...",
      "pair_cost": 0.92,
      "score": 0.78,
      "recommendation": "watch"
    }
  ]
}
```

## CLI Interface

```bash
# Basic run
python spikes/005-trend-intel/spike.py

# With config
python spikes/005-trend-intel/spike.py --config config.json

# Simulation mode (default, no live orders)
python spikes/005-trend-intel/spike.py --simulation

# Output to file
python spikes/005-trend-intel/spike.py --output spike-output.json

# Kill switch check
python spikes/005-trend-intel/spike.py --check-kill
```

## Implementation Plan

### Phase 1: Core Pipeline (MVP)

1. **Market Discovery**
   - Reuse spike 001 Gamma API polling
   - Add 15m Up/Down filter by slug pattern (`*-updown-15m-*`)
   - Support multiple assets (BTC, ETH, SOL, XRP)

2. **Inventory Reconstruction**
   - Reuse spike 002 logic
   - Fetch trade history via Polymarket data API
   - Compute pair_cost, balance_ratio, outcome_switches

3. **Structured Output**
   - JSON output to stdout and/or file
   - Include metadata (generated_at, regime, market_count)

### Phase 2: Intelligence Layer

4. **Regime Detection**
   - Calculate ADX for each asset from recent candles
   - Classify basket-wide regime
   - Borrow from AutoAgent's regime selector

5. **Opportunity Scoring**
   - Weighted score: pair_cost (40%), balance_ratio (30%), switches (20%), volume (10%)
   - Thresholds: high (>0.7), medium (0.4-0.7), low (<0.4)
   - Recommendation: watch / consider / avoid

### Phase 3: Safety & Operations

6. **Kill Switch Integration**
   - Check for KILL file before running
   - Exit with error if active
   - Log kill time to audit trail

7. **Audit Trail**
   - Write each scan to JSONL
   - Track which markets were scored
   - SQLite index for queries

8. **Configuration**
   - `config.json` for assets, thresholds, API URLs
   - Environment variables for API keys (if needed)

## Dependencies

- Existing: spikes 001, 002, 004
- New: lightweight ADX calculation (can use ta-lib or simple implementation)
- Polymarket APIs: Gamma (public), data API (public)

## Success Criteria

- [ ] Discovers all active 15m Up/Down markets for configured assets
- [ ] Computes pair cost and balance ratio for each market
- [ ] Detects regime (trending/chop) across basket
- [ ] Scores and ranks opportunities
- [ ] Outputs structured JSON
- [ ] Respects kill switch
- [ ] Writes audit trail
- [ ] Runs in simulation mode (no credentials required)

## Risks

| Risk | Mitigation |
|------|------------|
| Polymarket API rate limits | Add delays between requests, cache results |
| No edge in current strategies | Document this as observation tool, not execution system |
| Data completeness | Use public trade history, note gaps |
| Pair cost computation accuracy | Validate against known fixtures |

## Next Actions

1. Scaffold spike directory
2. Implement Phase 1 (core pipeline)
3. Run against live Polymarket data
4. Validate output schema
5. Add Phase 2 (intelligence layer)
6. Document findings in reports/

## References

- [Polymarket 15m Dump-and-Hedge Bot](https://medium.com/@Teraus/polymarket-15-minute-dump-and-hedge-bot-89018d7aa8fb)
- [Bot Research Analysis](../../bot-research.txt)
- [Spike 001 - Public Market Data](../001-public-market-data/README.md)
- [Spike 002 - Inventory Reconstruction](../002-inventory-reconstruction/README.md)
- [Spike 004 - Safety Patterns](../004-safety-patterns/README.md)
- [AutoAgent Regime Selector](https://github.com/marketcalls/AutoAgent)
- [CloddsBot Architecture](https://github.com/alsk1992/CloddsBot) — four-module trading system, risk engine, kill switch, opportunity finder
