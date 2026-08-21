# Medium Intel: Five Profitable Up/Down Bots

**Source:** `bot-research.txt`, supplied by Jay from the paywalled Coinsbench/Medium article at https://coinsbench.com/inside-the-mind-of-a-polymarket-bot-3184e9481f0a.  
**Live retrieval:** Coinsbench currently returns HTTP 403 to direct article requests. A Wayback entry dated 2026-05-15 19:27:40 UTC exists, but the returned archive page did not contain the article body; the user-saved text remains the primary content source.  
**Status:** Hypothesis source, not independently verified.  
**Claimed sample:** More than 1,000,000 August executions across five profitable Polymarket bots.

## Core thesis

The article argues that successful Up/Down bots are not primarily single-entry directional predictors. Their edge comes from sequential inventory management: average entry cost, paired quantity, directional remainder, balance between outcomes, order-book liquidity, fill size and timing.

This is directly useful. It suggests our first replay model must reconstruct complete market-level inventory rather than score isolated BUY records.

## Claimed strategy families

| Family | Identifier in supplied text | Claimed behaviour | Key claimed metrics | Main failure mode |
|---|---|---|---|---|
| Dynamic two-sided rotation | `0xce25e214d5cfe4f459cf67f08df581885aae7fdc` | Dynamically accumulates both outcomes across BTC/ETH/SOL/XRP 5m and 15m | Both sides in 93%; median pair cost 0.975; below 1 in 57% | One-way move prevents affordable hedge |
| Fixed-lot directional rotation | `0xAAAAA` | BTC 5m, mostly 60/120-contract blocks, repeatedly changes skew | Both sides in 96.3%; median pair cost 1.06; below 1 in 30%; balance ratio 64% | Late fixed block creates excess exposure or costly hedge |
| Balanced micro-fill accumulation | `x-MoneyForWhiskas` | BTC 5m; 50-contract core blocks plus micro-fills; repeated switching | Both sides in 98.7%; balance ratio 84%; pair cost 0.99; median 10 switches | Second side never reaches target price |
| Multi-timeframe regime switching | `bosona` | Different behaviour by timeframe and asset | Both sides in 43% of markets but 79% of volume; 5m pair cost 0.80; below 1 in 74% | Wrong regime selection |
| Directional core plus hedge | `mo-money` | Directional core with partial opposite-side overlay | Both sides in 41% but nearly 80% of volume; 5m balance ratio 58%; pair cost 0.81; below 1 in 71% | Incorrect hedge timing/size |

## What is testable

For each wallet/market/timeframe:

1. Reconstruct chronological fills.
2. Compute outcome quantities and volume-weighted average prices.
3. Compute paired quantity: `min(up_qty, down_qty)`.
4. Compute directional remainder and its outcome.
5. Compute pair cost: `up_vwap + down_vwap`.
6. Compute locked paired P&L: `paired_qty × (1 - pair_cost)` before fees.
7. Compute balance ratio: `min(qty) / max(qty)`.
8. Count switches between outcomes.
9. Recover likely parent orders by grouping adjacent fills at matching price/time.
10. Attribute results by wallet, asset, timeframe and path regime.
11. Revalue the position after every fill to measure temporary directional and cost risk.
12. Include taker/maker fees and executable order-book depth.

## Critical caveats

- Four account references are incomplete or human-readable labels, so the article alone is insufficient to reproduce the full sample.
- “Five most profitable” needs a defined ranking period, realised/unrealised accounting and capital denominator.
- The article does not provide raw executions, query code, fee assumptions or treatment of transfers/redemptions.
- Average Up + Down below 1 is not automatically executable arbitrage unless both quantities were fillable, retained and resolved together after costs.
- Public wallet fills do not reveal unfilled orders, cancellations, external hedges or parent-order intent.
- Profitable selection creates survivorship bias; we need losing/control wallets using the same reconstruction.
- Multiple fills may belong to one order, so raw fill counts overstate independent decisions.

## Initial hypotheses

- **H1:** Market-level pair cost and balance ratio explain results better than first-entry direction.
- **H2:** Balanced temporal accumulation has lower drawdown but depends more heavily on two-sided fill completion.
- **H3:** Directional-core systems earn more from residual exposure than locked pair P&L.
- **H4:** Five-minute systems use a different inventory regime from 15m/1h/4h systems.
- **H5:** Fixed lot size is structural and detectable from fill-size clustering.
- **H6:** Cheap pair formation is path-dependent; midpoint snapshots overstate the opportunity.
- **H7:** A strategy copied after observing wallet fills loses edge because follower fills are later and worse.

## Data required from the article/source

When available, capture:

- Original Medium URL/title/author/date.
- Complete wallet addresses for all five bots.
- Exact August year and UTC boundaries.
- Raw execution export or API query.
- Definition of profitability and starting capital.
- Fee/rebate treatment.
- Market identifiers and asset/timeframe parser.

## Build consequence

The lab should prioritize an **inventory reconstruction and replay engine** ahead of copying a directional signal. A first implementation now exists under `spikes/002-inventory-reconstruction/`; the next step is feeding it real wallet executions once full identifiers are available.
