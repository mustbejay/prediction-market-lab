# Initial Open-Source Shortlist Verdict

## Decision

Do **not** adopt a complete community trading bot as the lab foundation. Build a thin owned research service and borrow validated components.

### Selected references

1. **poly-maker — primary execution/microstructure reference**
   - 111 tests passed, 2 skipped; ruff clean.
   - Paper gateway and missing-wallet guard validated.
   - Explicit signer/funder/signature types and honest operational warnings.
   - Use its inventory skew, post-only quoting, rate limits, heartbeat and preflight ideas.
   - Do not use live from Great Britain or provide a funded key.

2. **PMXT — connector candidate, not yet accepted**
   - TypeScript core build passed.
   - Installation exposed dependency/test-runner drift; a forced test run had ESM/docs failures.
   - npm production audit reported 32 vulnerabilities: 13 low, 12 moderate, 7 high, 0 critical.
   - Keep isolated until a clean pinned install and public-data smoke pass.

3. **oracle3 — extract research math only**
   - Constraint-arbitrage arithmetic and selected execution/unwind behavior validated.
   - 591 tests passed but 19 failed; Windows persistence uses `Path.rename()` incorrectly.
   - Legacy Polymarket client/signature defaults are a custody concern.
   - Do not use its live execution layer.

4. **Weather Bot — extract ensemble prototype only**
   - Live 31-member GFS/Open-Meteo path works.
   - No repository tests; incorrect station/timezone handling, platform routing and weather calibration vocabulary.
   - Simulation flag is not an enforceable safety gate.
   - Do not adopt its scheduler/execution/accounting.

5. **Homerun — postpone**
   - Attractive replay/shadow architecture but large dependency surface and AGPL-3.0 licensing.
   - Initial audit timed out before a trustworthy test result.
   - Revisit only if our thin replay service proves insufficient.

## Owned build direction

Create a FastAPI/Python research backend with immutable public-data snapshots and deterministic inventory reconstruction. Keep venue adapters separate. A future Next.js dashboard consumes normalized research APIs.

## Immediate next milestone

Build a checkpointed wallet-history collector and market-level replay for the article's complete wallet. Add:

- Raw immutable API pages and deduplication.
- Timestamp/window completeness checks.
- BUY and SELL accounting.
- Resolution/redemption and realised P&L.
- Fees and maker rebates.
- Parent-order/fill grouping.
- Asset/timeframe attribution.
- Pathwise inventory and drawdown.
- Control-wallet comparison.

The existing 1,463-fill live sample already validates public ingestion and two-sided inventory reconstruction, but is not a profitability result.
