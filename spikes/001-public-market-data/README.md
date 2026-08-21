# 001: Public prediction-market data

## Question

Given no wallet or API credentials, can the lab discover active Polymarket markets and normalize enough executable metadata for research?

## Run

```bash
python main.py Bitcoin --output ../../data/bitcoin-latest.json
python main.py temperature --output ../../data/weather-latest.json
```

## Observable output

The CLI prints active markets ranked by reported 24-hour volume with liquidity, best bid, best ask, restriction status and question. It can save the normalized records as JSON.

## Safety

This spike calls only the public Gamma search endpoint. It contains no order endpoint, wallet support or authentication code.

## Verdict: VALIDATED

### What worked

- Live credential-free execution returned 58 active Bitcoin markets and 89 active weather markets.
- The normalized records include bid, ask, spread, liquidity, 24-hour volume, fee flag, restriction flag, outcomes, prices and resolution metadata.
- Snapshots were written to `data/bitcoin-latest.json` and `data/weather-latest.json`.
- Current results correctly expose `restricted: true`, reinforcing that this collector is research-only from Great Britain.

### What did not work cleanly

- A narrow `temperature` search returned no active markets while `weather` returned 89; discovery cannot rely on one keyword.
- Search results for `rain` included irrelevant phrase matches, so category/tag and rule-based classification are required before strategy research.

### Recommendation

Keep this public-data collector as a known-good baseline while evaluating PMXT and the larger bot frameworks. The next production-facing collector should use structured tags/categories rather than search text alone.
