from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

from .models import VenueMarket

BASE_URL = "https://api.limitless.exchange"
CHAIN_ID = 8453
USER_AGENT = "PredictionMarketLab/0.1 (read-only research)"


def _float_tuple(values: Any) -> tuple[float, ...]:
    return tuple(float(value) for value in (values or []))


def _properties(raw: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    result: dict[str, tuple[str, ...]] = {}
    for item in raw.get("properties") or []:
        key = str(item.get("propertyKeySlug") or "")
        if key:
            result[key] = tuple(str(value) for value in item.get("value") or [])
    return result


def normalize_market(raw: dict[str, Any]) -> VenueMarket:
    collateral = raw.get("collateralToken") or {}
    tokens = raw.get("tokens") or {}
    trade_prices = raw.get("tradePrices") or {}
    buy_prices = (trade_prices.get("buy") or {}).get("market") or []
    sell_prices = (trade_prices.get("sell") or {}).get("market") or []
    metadata = raw.get("metadata") or {}
    return VenueMarket(
        venue="limitless",
        chain_id=CHAIN_ID,
        market_id=str(raw.get("id")),
        condition_id=raw.get("conditionId"),
        title=str(raw.get("title") or ""),
        slug=str(raw.get("slug") or ""),
        status=str(raw.get("status") or ""),
        outcomes=("Yes", "No"),
        display_prices=_float_tuple(raw.get("prices")),
        market_buy_prices=_float_tuple(buy_prices),
        market_sell_prices=_float_tuple(sell_prices),
        outcome_tokens=(str(tokens.get("yes") or ""), str(tokens.get("no") or "")),
        collateral_symbol=str(collateral.get("symbol") or ""),
        collateral_address=str(collateral.get("address") or ""),
        trade_model=str(raw.get("tradeType") or ""),
        volume=float(raw.get("volumeFormatted") or 0),
        expiration_timestamp=(
            int(raw["expirationTimestamp"])
            if raw.get("expirationTimestamp") is not None
            else None
        ),
        categories=tuple(str(value) for value in raw.get("categories") or []),
        properties=_properties(raw),
        fees_enabled=bool(metadata.get("fee")),
        taker_delay_ms=int(metadata.get("takerDelayMs") or 0),
        maker_rebate_multiplier=float(metadata.get("makerRebateMult") or 0),
    )


class LimitlessPublicClient:
    def __init__(self, base_url: str = BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")

    def _get_json(self, path: str) -> Any:
        request = urllib.request.Request(
            self.base_url + path,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)

    def list_active_raw(
        self, page: int = 1, sort_by: str = "lp_rewards"
    ) -> dict[str, Any]:
        query = urllib.parse.urlencode(
            {"page": max(1, page), "limit": 25, "sortBy": sort_by}
        )
        payload = self._get_json(f"/markets/active?{query}")
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise TypeError("unexpected Limitless active-markets response")
        return payload

    def list_active_pages(
        self, max_pages: int = 1, sort_by: str = "lp_rewards"
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page in range(1, max(1, max_pages) + 1):
            payload = self.list_active_raw(page=page, sort_by=sort_by)
            page_rows = payload["data"]
            rows.extend(page_rows)
            total = int(payload.get("totalMarketsCount") or 0)
            if (total and len(rows) >= total) or (not total and len(page_rows) < 25):
                break
        return rows

    def list_active(
        self, max_pages: int = 1, sort_by: str = "lp_rewards"
    ) -> list[VenueMarket]:
        return [
            normalize_market(raw)
            for raw in self.list_active_pages(max_pages=max_pages, sort_by=sort_by)
        ]
