# Venue and Protocol Screen

**Date:** 2026-08-21  
**Purpose:** Avoid coupling the research and replay engine to Polymarket or any one frontend.  
**Compliance posture:** Operational accessibility is not legal confirmation. Every live adapter remains fail-closed until platform terms, UK applicability, technical behavior and explicit user activation are all verified.

## Atomic Wallet finding

Atomic Prediction Markets is **not an independent venue**. Atomic's official pages describe it as a built-in interface powered by Polymarket, with a dedicated USDC.e balance on Polygon held through a Polymarket proxy account.

Consequences:

- Atomic can provide a different interface and proxy-address UX.
- It does not provide an independent market, settlement system or liquidity source.
- Atomic does not explicitly claim UK users are legally eligible.
- It therefore does not solve Polymarket's Great Britain restriction for our architecture.

Official sources:

- https://atomicwallet.io/prediction-markets
- https://atomicwallet.io/blog/articles/atomic-prediction
- https://support.atomicwallet.io/article/399-what-is-polymarket
- https://support.atomicwallet.io/article/433-why-deposits-may-be-unavailable-for-prediction-wallets
- https://docs.polymarket.com/api-reference/geoblock

## Provider shortlist

| Provider | Protocol/frontend role | Chain/model | Programmatic access | UK status from official material | Lab decision |
|---|---|---|---|---|---|
| **Limitless** | On-chain venue plus frontend | Base (8453), USDC, CLOB | Public REST and WebSocket; active markets/order books require no auth | UK not explicitly banned in current terms, but local-law clause remains | **Integrate first, read-only** |
| **Azuro** | Protocol liquidity layer used by third-party apps | EVM, singleton LP/vAMM | SDK and subgraphs | No explicit UK statement located at protocol layer | **Research second** |
| **Overtime** | Sports frontend/protocol | EVM, sports AMM/pools | Live-market and quote APIs; contracts-v2 | No explicit UK statement located | **Research sports lane** |
| **Myriad** | On-chain prediction platform | Multiple EVM deployments | Public contracts; API exists but declares API-key auth | UK unclear | **Connector candidate** |
| **Opinion** | BNB-chain CLOB exchange | BNB Chain (56), order book | REST/WebSocket/OpenAPI, API key | UK unclear | **Connector candidate** |
| **Predict.fun** | BNB-native prediction venue | BNB Chain, outcome tokens | Contracts documented at a high level; developer API unclear | UK unclear | **Watch / contract research** |
| **SX Bet** | Sports order-book exchange | SX Network | Public API/contracts | Official terms explicitly prohibit United Kingdom | **Reject for UK execution** |
| **Drift BET** | Prediction product on Drift | Solana | Drift SDK/account discovery | Current activity and UK status not confirmed | **Deprioritize** |
| **Polymarket via Atomic** | Wallet frontend for Polymarket | Polygon, USDC.e, CLOB/proxy | Polymarket APIs | Great Britain close-only in Polymarket docs | **Research only** |

## Limitless live verification

The lab reached `https://api.limitless.exchange/markets/active` from the current host without authentication.

Verified API behavior:

- HTTP 200 JSON.
- `totalMarketsCount`: 628 at probe time.
- Hard page size: 25.
- Three-page integration smoke normalized 75 markets.
- 22 of those 75 carried the `crypto` domain property.
- All 75 in that sample had fee metadata enabled.
- Public response includes display prices, executable market buy/sell prices, token IDs, collateral, CLOB metadata, fees, taker delay, maker rebate multiplier, oracle details and properties.

A material microstructure finding: display probabilities can sum to one while executable market-buy prices sum materially above one. The normalizer therefore stores display and executable prices separately.

Official Limitless sources:

- https://docs.limitless.exchange/api-reference/introduction
- https://docs.limitless.exchange/api-reference/markets/browse-active
- https://docs.limitless.exchange/developers/programmatic-api
- https://docs.limitless.exchange/user-guide/terms-of-service
- https://api.limitless.exchange/markets/active
- https://github.com/limitless-labs-group/Limitless-Exchange
- https://github.com/limitless-labs-group/limitless-exchange-go-sdk

## Other official developer sources

Azuro:

- https://gem.azuro.org/knowledge-hub/introduction/what-is-azuro
- https://gem.azuro.org/knowledge-hub/how-azuro-works/protocol-actors/liquidity-providers
- https://github.com/Azuro-protocol/sdk
- https://github.com/Azuro-protocol/Azuro-subgraphs

Overtime:

- https://docs.overtimemarkets.xyz/overtime-v2-integration/overtime-v2-live-markets
- https://docs.overtimemarkets.xyz/overtime-v2-integration/overtime-v2-quote-data
- https://docs.overtimemarkets.xyz/sports-amm-smart-contract
- https://github.com/thales-markets/contracts-v2

Myriad:

- https://docs.myriad.markets/
- https://docs.myriad.markets/builders/contract-addresses
- https://myriad.markets/markets

Opinion:

- https://docs.opinion.trade/
- https://docs.opinion.trade/trade-on-opinion.trade/trade-on-prediction-market/understanding-the-order-book
- https://app.opinion.trade/

Predict.fun:

- https://docs.predict.fun/
- https://docs.predict.fun/terms-of-service
- https://predict.fun/

SX Bet:

- https://docs.sx.bet/api-reference/introduction
- https://help.sx.bet/en/articles/3613372-terms-and-conditions
- https://github.com/sx-bet/smart-contracts

## Immediate build order

1. Limitless public market and order-book adapter.
2. Common normalized market, outcome, executable-price and policy models.
3. Fail-closed execution policy with four required gates.
4. Azuro subgraph/SDK feasibility spike.
5. Overtime live-market/quote adapter for sports.
6. Myriad/Opinion connector feasibility after API-key and terms review.
7. Cross-venue contract-equivalence and price-dislocation engine.

No live execution is enabled.
