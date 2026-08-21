# Prediction Market Lab

An isolated, credential-free evaluation lab for prediction-market infrastructure and open-source bots.

## Current objective

Reproduce what shortlisted projects can actually do before selecting a foundation for a read-only market collector, replay simulator, paper trader, and opportunity scanner.

## Safety rules

- No funded wallets, API secrets, private keys, or live order permissions.
- Do not bypass geographic or platform restrictions.
- Prefer public market data, fixtures, unit tests, paper mode, replay, and shadow execution.
- Never count midpoint-only P&L as executable.
- Treat repository profit claims as unverified until reproduced from fills.
- Do not modify the vendored repositories except in clearly named throwaway experiment copies.

## Evaluation gates

1. **Provenance:** active project, clear licence, pinned dependencies, understandable ownership.
2. **Installation:** clean install on Windows or documented container path.
3. **Security:** no key exfiltration, unsafe shell execution, hidden downloads, or withdrawal capability.
4. **Data:** live public-data or reproducible fixture ingestion.
5. **Simulation:** dry-run, shadow, paper, or deterministic replay.
6. **Execution realism:** bid/ask, fees, partial fills, latency and rejected orders.
7. **Strategy evidence:** tests and reproducible output, not screenshots or README claims.
8. **Fit:** supports a Next.js/FastAPI intelligence product without forcing live trading.

## Initial candidates

- PMXT — multi-venue integration layer.
- Homerun — research/backtest/shadow platform.
- poly-maker — market-making risk-control reference.
- oracle3 — probability pricing and constraint-arbitrage research.
- Polymarket/Kalshi Weather Bot — ensemble weather prototype.

Vendored source is stored under `vendor/` and excluded from this repository. Results belong under `spikes/` and `reports/`.
