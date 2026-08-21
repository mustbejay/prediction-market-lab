# 002: Inventory reconstruction

## Question

Can we convert chronological Up/Down fills into the inventory metrics described in Jay's Medium article?

## Implemented

- Outcome quantities and VWAPs.
- Paired quantity.
- Balance ratio.
- Combined pair cost.
- Locked paired P&L before fees.
- Directional remainder.
- Outcome-switch count.
- CSV grouping by market.
- Validation for mixed markets, invalid prices, invalid sizes and unknown outcomes.

## Run

```bash
python -m unittest -v test_reconstruct.py
python reconstruct.py fixtures/article-examples.csv
```

## Verified output

- Four unit tests passed.
- The article's 250 Up / 145 Down example reconstructs as:
  - 145 paired contracts.
  - 105 Up directional remainder.
  - 58% balance ratio.
  - 0.81 pair cost using the synthetic 0.40/0.41 prices.
  - $27.55 locked paired P&L before fees.
- A balanced 50/50 synthetic path at 0.44/0.53 reconstructs to a 0.97 pair cost and $1.50 locked paired P&L before fees.

## Verdict: VALIDATED FOR BUY-SIDE INVENTORY

The basic accounting works and is now test-backed. It is not yet a complete wallet replay engine: sells, redemptions, fees/rebates, market resolution, external hedges, parent-order grouping and mark-to-market path risk remain to be implemented after obtaining real execution data and complete wallet identifiers.
