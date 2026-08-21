from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VenueMarket:
    venue: str
    chain_id: int
    market_id: str
    condition_id: str | None
    title: str
    slug: str
    status: str
    outcomes: tuple[str, ...]
    display_prices: tuple[float, ...]
    market_buy_prices: tuple[float, ...]
    market_sell_prices: tuple[float, ...]
    outcome_tokens: tuple[str, ...]
    collateral_symbol: str
    collateral_address: str
    trade_model: str
    volume: float
    expiration_timestamp: int | None
    categories: tuple[str, ...]
    properties: dict[str, tuple[str, ...]]
    fees_enabled: bool
    taker_delay_ms: int
    maker_rebate_multiplier: float
