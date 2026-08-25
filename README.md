# Prediction Market Lab

Venue-agnostic prediction market research, backtesting, and paper trading system.

**Status:** Backtesting complete. Ready for paper trading once terms/jurisdiction confirmed.

## Architecture

```
┌─────────────────────────────────────────────┐
│           Command Center                    │
│  Discovery → Inventory → Regime → Scoring   │
└─────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────┐
│           Safety Layer                      │
│  KillSwitch + AuditTrail (fail-closed)      │
└─────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────┐
│           Venues                            │
│  Polymarket (CLOB) | Limitless (Base)       │
└─────────────────────────────────────────────┘
```

## Backtest Results

### Limitless (300 snapshots, 272 lifecycles)
| Strategy | N | Hit % | Avg P&L/share |
|----------|---|-------|---------------|
| H7 [0.5-0.6] | 42 | 67% | **+0.068** |
| H2 Late fav | 132 | 89% | **+0.023** |
| H3 Momentum | 84 | 86% | **+0.022** |

### Polymarket (130 wallet markets)
| Metric | Value |
|--------|-------|
| Two-sided % | 86.9% |
| Median pair cost | **0.83** (-17%) |
| Pairs < 1.0 | 77% |
| Net edge (H7) | **+0.066/share** |

### Fee Comparison
| Venue | Pair Cost | Arb Windows | Best For |
|-------|-----------|-------------|----------|
| Limitless | +8.5% | 0% | Niche directional |
| Polymarket | **-17%** | **77%** | Momentum + Hedging |

## Installation

```bash
cd prediction-market-lab
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

## Running Analysis

```bash
# Run hypothesis battery on Limitless data
python scripts/hypothesis_battery_full.py

# Compare venue fees
python scripts/scanner.py --compare

# Live scanner (scans Polymarket every 2 runs)
python scripts/scanner.py --runs 3
```

## Data

- `data/snapshots/` — Limitless hourly snapshots (300 files)
- `data/wallet-ce25-sample.json` — Polymarket wallet trade history
- `scan-history.jsonl` — Command center scan logs

## Safety

All execution is **fail-closed** by default:
1. Create `KILL` file to halt all operations
2. All scans logged to `audit/orders.jsonl`
3. Execution policy requires 4 approvals

## Repositories

| Repo | Purpose |
|------|---------|
| [prediction-market-lab](https://github.com/mustbejay/prediction-market-lab) | This repo — backtesting, analysis, research |
| [Predictions-Lab-tablet](https://github.com/mustbejay/Predictions-Lab) | Production tablet agent with execution framework |

## Next Steps

1. Paper trade H7 on Polymarket (small size)
2. Add real-time WebSocket feed
3. Build automated execution once legal review complete
4. Expand to Kalshi, Hyperliquid, other venues
