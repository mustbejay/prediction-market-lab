# Venue-Agnostic Architecture

## Principle

Strategies consume normalized markets and inventory events. They never import a venue-specific API client directly.

```text
Provider APIs / subgraphs / contracts
             │
      read-only adapters
             │
      normalized market model
             │
  snapshots · replay · fair value · alerts
             │
       execution policy gate
             │
 venue-specific executor (disabled by default)
```

## Separation of concerns

### Operator vs frontend

Record both separately. Atomic Wallet is a frontend/access layer whose operator and liquidity source is Polymarket. A different UI does not create a different venue or jurisdictional status.

### Market data vs execution

Every provider can independently support:

- Public discovery.
- Public order book.
- Public trades.
- Wallet activity.
- Historical data.
- Paper execution.
- Authenticated execution.

A missing capability must not be silently emulated.

### Display vs executable probability

Store separately:

- Display/last/mid prices.
- Best bid/ask.
- Market-buy and market-sell estimates.
- Fees, rebates and delay.

Never use display probabilities as executable pair cost.

## Live execution gate

Execution is fail-closed unless all four values are explicit:

1. Platform terms allow the user.
2. Jurisdiction has been verified.
3. The adapter and custody path have passed tests.
4. Jay explicitly enables that venue.

The implementation is `src/prediction_lab/venues/policy.py`; defaults block execution.

## First adapter

`src/prediction_lab/venues/limitless.py` currently provides:

- Credential-free active-market discovery.
- 25-row pagination.
- Normalization to the common `VenueMarket` model.
- Display and executable-price separation.
- Base chain/collateral metadata.
- Fee, taker-delay, maker-rebate and property metadata.

Six Limitless tests and three execution-policy tests pass. Live smoke normalized 75 markets across three pages.
