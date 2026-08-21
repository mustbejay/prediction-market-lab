# Limitless API Credential Setup

**Date:** 2026-08-21  
**Credential source:** Proton Pass vault `Crypto`, item `Limitless - Predictions`.  
**Secret handling:** Values were retrieved field-by-field with an audited access reason, were not printed, and were installed in the ignored local file `.secrets/limitless.env`.

## Discovered fields

- `API Key`
- `Secret`
- `Permissions`
- `website`
- `Wallet address`

Only `API Key` and `Secret` were retrieved. No wallet private key was requested or stored.

## Verification

The official `@limitless-exchange/sdk` `HttpClient` was initialized with HMAC credentials:

- Token ID from `LIMITLESS_API_KEY`.
- Base64 HMAC secret from `LIMITLESS_API_SECRET`.
- Base URL `https://api.limitless.exchange`.

Read-only authenticated request:

```text
GET /portfolio/trades
```

Result:

```json
{"authenticated": true, "type": "array", "count": 0}
```

This proves the API key and secret authenticate successfully. It does not enable or validate order placement. The public adapter remains read-only, and the execution policy remains fail-closed.

`GET /auth/api-tokens/capabilities` was not a valid HMAC probe because that endpoint requires Privy authentication; this was an endpoint-auth-mode mismatch, not a credential failure.
