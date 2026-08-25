# Historical Data Added

**Date:** 2026-08-25  
**Source:** Wallet `0xce25e214d5cfe4f459cf67f08df581885aae7fdc`

---

## Dataset Summary

| File | Markets | Collected | Source |
|------|---------|-----------|--------|
| `bitcoin-latest.json` | 58 | 2026-08-21 | Polymarket Gamma API |
| `rain-latest.json` | 126 | 2026-08-21 | Polymarket Gamma API |
| `wallet-ce25-sample.json` | 130 | 2026-08-21 | On-chain trade history |
| `weather-latest.json` | 89 | 2026-08-21 | Polymarket Gamma API |

---

## Key Findings: Wallet 0xce25

### Pair Cost Analysis
- **Median pair cost: 0.83** (vs theoretical 1.00)
- **77% of pairs cost < 1.0** — actionable arbitrage window
- Average "discount" when buying both sides: 17%

### Position Structure
- **86.9% two-sided** (hold both Up and Down)
- **Median balance ratio: 0.78** (moderate imbalance)
- **Median switches: 3** per market lifecycle

### Interpretation
The data shows a market where:
1. Counterparties are often willing to sell cheaply (pair cost < 1.0)
2. Sophisticated traders hold both sides and rebalance periodically
3. This creates natural liquidity for hedging strategies

---

## Backtesting Opportunity

With this data, we can now:

1. **Test hypothesis H5** (underdog value): Buy Up at 0.30-0.45, see win rate
2. **Test hypothesis H7** (0.5 discontinuity): Momentum around median
3. **Validate pair cost strategy**: Buy both sides when pair_cost < 0.95
4. **Measure actual P&L** including fees and slippage

---

## Next Steps

1. Run hypothesis battery on this wallet data
2. Compare Limitless vs Polymarket pair costs
3. Build backtest engine using `analyze_lifecycles.py` pattern
4. Add real-time data collection to maintain fresh dataset
