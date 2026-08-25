# Spike 005: Trend Intel Command Center - Summary

## Status
Completed. All tests passing (27/27).

## Files Created

| File | Description |
|------|-------------|
| `spikes/005-trend-intel/spike.py` | Main implementation (21KB) |
| `spikes/005-trend-intel/README.md` | Specification document |
| `spikes/005-trend-intel/NOTES.md` | Research notes |
| `tests/test_spike_005_import.py` | Import tests |
| `tests/test_trend_intel.py` | Unit tests (15 tests) |
| `tests/test_spike_005_integration.py` | Integration tests (3 tests) |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Trend Intel Command Center                │
├─────────────────────────────────────────────────────────────┤
│  Phase 1: Market Discovery                                   │
│    • Fetch from Polymarket Gamma API                        │
│    • Filter by Up/Down pattern: -(btc|eth|sol|xrp)-updown- │
│      (5m|15m|1h|4h|1d)-<timestamp>                         │
│    • Return normalized market dicts                          │
│                                                              │
│  Phase 2: Inventory Reconstruction                          │
│    • Fetch trade history from Data API                      │
│    • Compute: pair_cost, balance_ratio, paired_quantity     │
│    • Handle edge cases (no data, invalid prices)            │
│                                                              │
│  Phase 3: Regime Detection                                   │
│    • Classify: chop, balanced, trending, trending_strong    │
│    • Based on median pair cost across basket                │
│                                                              │
│  Phase 4: Opportunity Scoring                                │
│    • Weighted composite: pair_cost (40%), balance (30%)     │
│      switches (20%), volume (10%)                           │
│    • Output: score (0-1), recommendation (watch/consider/  │
│      avoid), opportunity tier (high/medium/low)             │
│                                                              │
│  Safety Layer                                                │
│    • KillSwitch: file-based halt (KILL file)                │
│    • AuditTrail: JSONL log of scans                         │
│    • Simulation mode: no live execution                     │
└─────────────────────────────────────────────────────────────┘
```

## Key Features

1. **Multi-timeframe support**: 5m, 15m, 1h, 4h, 1d
2. **4-asset coverage**: BTC, ETH, SOL, XRP
3. **Kill switch integration**: From spike 004
4. **Audit trail**: JSONL logging with scan metadata
5. **Structured JSON output**: For downstream consumption
6. **Simulation mode**: Safe for testing

## Test Results

```
tests/test_spike_005_import.py::test_imports PASSED
tests/test_spike_005_import.py::test_inventory_metrics_creation PASSED
tests/test_trend_intel.py::TestKillSwitch::* (5 tests) PASSED
tests/test_trend_intel.py::TestDetectRegime::* (4 tests) PASSED
tests/test_trend_intel.py::TestScoreMarket::* (3 tests) PASSED
tests/test_trend_intel.py::TestAuditTrail::test_log_creates_file PASSED
tests/test_spike_005_integration.py::test_run_command_center_returns_result PASSED
tests/test_spike_005_integration.py::test_discover_markets_filters_correctly PASSED
tests/test_spike_005_integration.py::test_kill_switch_integration PASSED
tests/test_venue_policy.py::* (3 tests) PASSED
```

**Total: 27 passed, 0 failed**

## Usage

```bash
# Run with defaults
python spikes/005-trend-intel/spike.py

# Check kill switch only
python spikes/005-trend-intel/spike.py --check-kill

# Save output to file
python spikes/005-trend-intel/spike.py --output result.json

# Custom assets
python spikes/005-trend-intel/spike.py --assets btc eth

# Custom kill switch path
python spikes/005-trend-intel/spike.py --kill-path /path/to/KILL
```

## Next Steps (Phase 2)

- [ ] Add real-time WebSocket feed for live price updates
- [ ] Implement orderbook imbalance detection (from CloddsBot)
- [ ] Add historical backtesting against saved scan data
- [ ] Export to CSV/Parquet for analysis
- [ ] Add alerting (email/Telegram/Discord) on high-opportunity signals

## Open Questions

1. Should we implement the dump-hedge strategy itself, or just observe/score?
   - Recommendation: observe first, validate edge before considering execution
2. How to handle markets with no trade history?
   - Currently returns empty metrics, scored as 0. Consider skipping or flagging.
3. Timeframe selection - should we focus on 5m only or include 15m?
   - Current default: both 5m and 15m. Can configure via `timeframes` param.

## References

- [OpenAlgo Kill Switch Pattern](https://github.com/marketcalls/openalgo)
- [AutoAgent Regime Selector](https://github.com/marketcalls/AutoAgent)
- [CloddsBot Architecture](https://github.com/alsk1992/CloddsBot) — four-module trading system, risk engine, kill switch, opportunity finder
- [Polymarket 15m Dump-and-Hedge Bot](https://medium.com/@Teraus/polymarket-15-minute-dump-and-hedge-bot-89018d7aa8fb)

## Key Learnings

1. Polymarket Gamma API returns events, not direct markets — need to iterate through events > markets
2. Up/Down markets have consistent slug pattern: `-{asset}-updown-{timeframe}-{timestamp}`
3. Trade history API (`/trades`) returns empty for many markets — fallback to using best_bid/best_ask from market data
4. Pair cost < 0.95 is the key threshold for dump-hedge viability
5. Kill switch file pattern is simple but effective — survives restarts, easy to audit
