# 003: Public wallet execution sample

## Question

Can the lab retrieve public fills for the complete wallet supplied in the Coinsbench article and calculate the article's inventory metrics without credentials?

## Verified live run

Wallet: `0xce25e214d5cfe4f459cf67f08df581885aae7fdc`  
Data API: `https://data-api.polymarket.com/trades`  
Sample: three pages of 500 rows, deduplicated to 1,463 public fills.

The sample covered 130 Up/Down markets. To reduce pagination-boundary bias, the primary subset retains only markets whose complete encoded 5m/15m/1h/4h interval lies inside the collected timestamp range.

### Complete-window results

- 117 markets.
- 105 two-sided markets.
- Two-sided share: **89.74%**.
- Median combined Up/Down VWAP: **0.8309**.
- Pair cost below one: **78.10%** of two-sided markets.
- Median balance ratio: **78.17%**.
- Median outcome switches: **3**.

These values show the article's qualitative mechanism is observable in current public data, but they do **not** reproduce its August headline statistics. This is a short recent sample, the API shifts while a very active wallet trades, and fees, redemptions, sells, rebates and parent-order grouping are not yet included.

## Run

```bash
python analyze.py 0xce25e214d5cfe4f459cf67f08df581885aae7fdc \
  --pages 3 --page-size 500 \
  --output ../../data/wallet-ce25-sample.json
python -m unittest -v test_analyze.py
```

## Verdict: VALIDATED FOR PUBLIC SAMPLE INGESTION

We can now fetch and reconstruct a real target wallet without credentials. Next, build a stable historical collector with timestamp checkpoints, raw immutable pages, resolution/redemption accounting and fee/rebate treatment before drawing profitability conclusions.
