# Spike 005: Trend Intel Command Center - Notes

## Sources Reviewed (2026-08-24)

### Teraus's Polymarket 15m Dump-and-Hedge Bot

**What it does:**
- Trades 15m Up/Down binary markets on Polymarket
- Strategy: buy side that dumped (ask drops ≥15% in 3s), hedge when pair cost ≤ 0.95
- Stop-loss if hedge doesn't arrive before 5min remaining
- Modes: simulation (default), production, redeem-only

**Key implementation details:**
- Uses Polymarket CLOB API + Gamma API
- Discovers markets by slug pattern: `btc-updown-15m-<timestamp>`
- Config-driven: `config.json` with API keys, private key, trading parameters
- Rust implementation, PM2-ready

**Relevance to our project:**
- Directly applicable to our 15m Up/Down market focus
- Simulation mode aligns with our safety-first approach
- Pair cost threshold (0.95) is a concrete example of opportunity scoring

### Teraus's Raydium Volume Bot

**What it does:**
- Solana multi-wallet volume bot for Raydium DEX
- Distributes SOL across sub-wallets, executes buy/sell swaps
- Features: massive buy mode, gradual sell mode, random amounts

**Relevance:** Low — degen Solana tool, not applicable to prediction markets.

### Bot Research Analysis (bot-research.txt)

Analysis of 1M+ executions from top 5 Polymarket bots reveals:

**Common patterns across all bots:**
1. Up and Down are two parts of the same inventory (not independent positions)
2. They trade the price path, not single snapshots
3. Sizing is part of the algorithm, not just risk control

**Bot-specific patterns:**
| Bot | Approach | Pair Cost | Balance |
|-----|----------|-----------|---------|
| 0xcE25E214… | Dynamic rotation | ~$0.975 | Flexible |
| 0xAAAAA | Fixed 120-contract lots | ~$1.06 | Directional |
| x-MoneyForWhiskas | Micro-fill accumulation | ~$0.99 | Balanced (84%) |
| bosona | Multi-timeframe switching | $0.80 (5m) → $1.00+ (1h) | Regime-dependent |
| mo-money | Directional core + hedge | ~$0.81 (5m) | 58% smaller side |

**Key insight:** The edge isn't in a single signal — it's in inventory structure management. Different bots use different approaches, but all manage both sides dynamically.

### CloddsBot (Reference Architecture)

Comprehensive AI trading terminal (739 stars, MIT license) built for prediction markets and crypto.

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
2. **Opportunity Finder** — cross-platform arbitrage with semantic entity matching
3. **Orderbook Imbalance Detector** — calculates `imbalanceScore`, `bidAskRatio`, `signal`, `confidence`
4. **Kill Switch** — immediate halt of all bots, blocks new trades, persisted to SQLite
5. **A/B Testing** — run same strategy on multiple accounts to test variations

**Why this matters:** CloddsBot demonstrates that a well-structured trading system needs four separate concerns (execution, bot management, safety, opportunity finding) with clear interfaces between them. Our spike should adopt this modularity rather than building a monolithic script.

## Spike 005 Specification

Created comprehensive spec in:
- `spikes/005-trend-intel/README.md` (project)
- `Trading/Spike-005-Trend-Intel-Command-Center.md` (Obsidian)

**Core concept:** Command center that wires spikes 001-004 together to provide unified visibility into 15m Up/Down market opportunities.

**Three layers:**
1. **Core pipeline** (reuse existing): market discovery, inventory reconstruction, structured output
2. **Intelligence layer** (new): regime detection (ADX), opportunity scoring (pair cost, balance ratio, switches)
3. **Safety layer** (reuse): kill switch, audit trail

**Output:** Structured JSON with regime classification, market scores, top opportunities, recommendations.

**Modular design (inspired by CloddsBot):**

| Module | Responsibility | Our spike equivalent |
|--------|----------------|----------------------|
| ExecutionService | orders, fills, tracking | Not yet (read-only for now) |
| BotManager | strategies, signals, execution | OpportunityScorer |
| SafetyManager | breakers, drawdown, kill switch | KillSwitch + AuditTrail |
| OpportunityFinder | arbitrage, matching, scoring | RegimeDetector + OpportunityScorer |

## Next Steps

- [ ] Scaffold spike directory
- [ ] Implement Phase 1: core pipeline (market discovery + inventory reconstruction)
- [ ] Run against live Polymarket data
- [ ] Validate output schema
- [ ] Add Phase 2: regime detection + opportunity scoring
- [ ] Integrate kill switch + audit trail from spike 004

## Open Questions

1. Should we implement the dump-hedge strategy itself, or just observe/score?
   - Recommendation: observe first, validate edge before considering execution

2. How do we handle API rate limits for trade history fetches?
   - Need to test Polymarket data API limits

3. Should regime detection use ADX or a simpler heuristic?
   - ADX is standard but requires historical candles
   - Could start with pair cost volatility as proxy
