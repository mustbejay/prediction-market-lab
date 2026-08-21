# poly-maker and oracle3 Audit

## poly-maker

**Commit:** `4f32103591c9582ccd012bdf10f77d86e5879444`  
**Verdict:** VALIDATED as a paper-execution and market-making reference; not a proven profitable strategy.

- `pytest`: 111 passed, 2 skipped.
- `ruff`: clean.
- CLI loads with 12 subcommands.
- Paper gateway creates synthetic order IDs without invoking the live client.
- Missing wallet in non-paper mode raises a runtime guard.
- Signature/funder distinction is explicit.
- Operational caveat: concurrent engines on one wallet can race/double-order.

## oracle3

**Commit:** `86c2518a981e8c7d4738a54dd9eff1b1468bb527`  
**Verdict:** PARTIAL; useful research math, unsuitable as our live execution base.

- `pytest`: 591 passed, 19 failed, 1 skipped.
- `ruff`: clean with one stale warning.
- Public Polymarket market listing works without credentials.
- Constraint-arbitrage and selected unwind logic reproduced.
- Windows persistence failures stem from `Path.rename()` replacing an existing target.
- CLI strategy-loader failures remain.
- Full simulation has undeclared pandas dependency drift.
- Legacy `py-clob-client` and EOA-default signature/funder behavior create a custody/settlement concern.

No credentials or live modes were used. Vendored source was not intentionally modified.
