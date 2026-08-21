# Polymarket/Kalshi Weather Bot Audit

**Date:** 2026-08-21  
**Repository:** `vendor/weather-bot`  
**Commit audited:** `e406394d59c208cc035c4fdf37ebb26636e15a47`  
**Credential policy:** No trading credentials configured or added; no live mode enabled.

## Verdict

**PARTIAL** for the lab. The credential-free weather forecast/signal path is runnable and the 31-member Open-Meteo GFS ensemble calculation works against the live free endpoint. However, the claimed end-to-end Polymarket/Kalshi weather bot is not validated: there are no repository tests, simulation mode is not enforced by the execution paths, Kalshi weather trades are stored as Polymarket, and calibration accuracy is incorrect for weather `yes`/`no` signals.

## What was run

All commands were run from `C:/Users/user/prediction-market-lab/vendor/weather-bot`.

- `git rev-parse HEAD` → `e406394d59c208cc035c4fdf37ebb26636e15a47`
- `python -m compileall -q backend main.py run.py` → exit `0`
- Installed missing local dependency only: `SQLAlchemy==2.0.25`. No source files changed.
- Imported FastAPI app and initialized SQLite schema: `fastapi_routes 27`, `db_init_ok`.
- Live no-credential weather fetch: `fetch_ensemble_forecast('nyc', today)` returned `31` highs and `31` lows, mean high `82.9F`.
- No-credential Kalshi path: `kalshi_credentials_present False`; `fetch_kalshi_weather_markets(['nyc'])` returned `0` without attempting auth.
- Polymarket weather discovery completed without credentials and returned `0` markets in this run (network/API availability is not treated as a strategy failure).
- Fixture signal smoke: 28/31 members above 75F and market YES 60c produced model probability `0.903226`, edge `0.303226`, direction `yes`, threshold pass `True`, size `$75.0`, source `open_meteo_ensemble_31m`.
- Fixture parser smoke passed representative New York/NYC/Miami/Denver titles and dates.
- Kelly smoke: both an 80% YES at 60c and a 20% probability DOWN case returned `$75`, consistent with configured fractional-Kelly plus BTC hard cap in the tested helper.

## Findings

### 31-member GFS/Open-Meteo method — PARTIAL PASS

- `backend/data/weather.py` requests `https://ensemble-api.open-meteo.com/v1/ensemble` with `models=gfs_seamless`, daily max/min, Fahrenheit, and one target date.
- It collects the control plus member keys and the live response yielded exactly 31 high and 31 low values.
- Probabilities are strict `>` threshold fractions. This is appropriate only if the market contract is strictly “above”; inclusive or bracket contracts need explicit semantics.
- The fallback on missing data is `0.5`, which is safe for probability but callers skip forecasts when member arrays are empty.

### Exact station/resolution handling — NOT VALIDATED

- Forecast coordinates are city centroids, not the settlement stations listed in the README (`KNYC`, `KORD`, `KMIA`, `KLAX`, `KDEN`). The station IDs are used only for NWS observations.
- NWS settlement uses UTC midnight-to-midnight observation queries and takes max/min of returned observations. It does not convert to the station’s local calendar day, does not clearly enforce the official market station contract, and has no explicit pagination/coverage validation.
- Polymarket resolution is interpreted from `outcomePrices` and market `closed`; this is not independently checked against the market’s actual resolution rules.
- Kalshi resolution is queried correctly by ticker only when credentials exist, but no authenticated test was performed by design.

### Market parsing/discovery — PARTIAL

- Representative title parsing worked.
- The Polymarket discovery loop repeats the same `tag=Weather` request three times for different unused `search_term` values. The first loop appends without deduplication, so duplicate markets/signals are possible.
- Parser defaults direction to `above`; titles containing “at or below”, “not above”, or equivalent language can be misclassified. Threshold regex only accepts unsigned integer Fahrenheit values.
- Kalshi ticker parsing supports `KXHIGH...-YYMONDD-B/Tnn.n` and high-temperature markets only. It does not validate the series prefix against `city_key` inside the parser.

### Simulation and execution safety — FAIL / SECURITY CONCERN

- `SIMULATION_MODE=True` by default, but it is not used as a gate in `scan_and_trade_job` or `weather_scan_and_trade_job`; those paths directly create persisted `Trade` records whenever the bot state is running. No real order-placement implementation was found, so this is currently paper-ledger behavior, but the mode flag is not an enforceable safety boundary.
- `/api/simulate-trade` is explicitly a manual paper-trade endpoint, but it rescans live BTC markets and does not support weather despite the project’s weather claims.
- Weather scheduler creates every weather trade with `platform="polymarket"`, even for Kalshi markets. This can route Kalshi weather settlement through the Polymarket resolver and is a material accounting/settlement defect.
- The scheduler applies a minimum `$10` trade size after Kelly sizing, potentially creating a trade even when suggested Kelly size is zero/very small (provided the signal passed); this weakens strict risk sizing.
- No credentials, key files, or live trading modes were configured.

### Calibration/Brier logic — PARTIAL / WEATHER BUG

- Brier score calculation itself uses `(model_probability - settlement_value)^2`, where weather model probability is YES and settlement is 1/0, which is conceptually appropriate.
- Settlement links set `actual_outcome` to `up` or `down` for all signals. Weather signals use `yes`/`no`; therefore weather `outcome_correct = (direction == actual_outcome)` is always false for normal weather signals, corrupting accuracy and actual-edge summaries.
- The calibration summary substitutes `0.5` if settlement value is missing, although settled signals should require a known binary outcome; this can hide data-quality errors.
- There is no Brier test suite, calibration persistence test, or backtest.

### Tests and security

- No test files were present (`search_files` found no `test*` files).
- Python bytecode compilation passed.
- Secrets are read from environment/path and no hard-coded private key was found in the audited files. The sample NWS User-Agent uses `contact@example.com`, which is poor operational hygiene.
- SQLite defaults to a working-directory file; this created generated artifact `vendor/weather-bot/tradingbot.db` during schema smoke. It is untracked and was not committed or treated as source.

## Generated/modified files

- Created by the audit: `C:/Users/user/prediction-market-lab/reports/weather-bot.md`.
- Generated during smoke test: `vendor/weather-bot/tradingbot.db` (untracked SQLite database; source was not modified).
- No repository source files were modified. Local dependency installation changed only the environment.

## Recommended fixes before VALIDATED

1. Make `SIMULATION_MODE` an explicit, tested execution gate; separate paper ledger from any future order client and default all platform actions to no-op without an explicit allow-list.
2. Preserve `market.platform` when creating weather trades and route settlement by platform.
3. Normalize outcome vocabulary (`yes/no` vs `up/down`) before setting calibration fields; add weather Brier/accuracy tests.
4. Define and implement exact settlement station/time-zone/observation rules, including coverage and pagination checks.
5. Deduplicate Polymarket discovery requests/results and expand parser tests for inclusive/below/bracket wording, signed/decimal thresholds, and explicit years.
6. Add deterministic unit tests for ensemble member counting, edge/Kelly sizing, parser semantics, simulation safety, platform routing, settlement, and calibration.
