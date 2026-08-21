import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from prediction_lab.venues.limitless import LimitlessPublicClient, normalize_market


class LimitlessNormalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        path = ROOT / "tests" / "fixtures" / "limitless-market.json"
        cls.raw = json.loads(path.read_text(encoding="utf-8"))

    def test_normalizes_common_venue_market(self) -> None:
        market = normalize_market(self.raw)
        self.assertEqual(market.venue, "limitless")
        self.assertEqual(market.chain_id, 8453)
        self.assertEqual(market.market_id, "368889")
        self.assertEqual(market.outcomes, ("Yes", "No"))
        self.assertEqual(market.display_prices, (0.195, 0.805))
        self.assertEqual(market.collateral_symbol, "USDC")
        self.assertEqual(market.trade_model, "clob")
        self.assertEqual(market.volume, 11.32)

    def test_keeps_executable_prices_separate_from_display_prices(self) -> None:
        market = normalize_market(self.raw)
        self.assertEqual(market.market_buy_prices, (0.26, 0.87))
        self.assertEqual(market.market_sell_prices, (0.13, 0.74))
        self.assertAlmostEqual(sum(market.display_prices), 1.0)
        self.assertAlmostEqual(sum(market.market_buy_prices), 1.13)

    def test_exposes_execution_and_fee_metadata(self) -> None:
        market = normalize_market(self.raw)
        self.assertTrue(market.fees_enabled)
        self.assertEqual(market.taker_delay_ms, 250)
        self.assertEqual(market.maker_rebate_multiplier, 0.3)
        self.assertEqual(market.properties["ticker"], ("btc",))


class StubClient(LimitlessPublicClient):
    def __init__(self) -> None:
        super().__init__()
        self.paths: list[str] = []

    def _get_json(self, path: str):
        self.paths.append(path)
        page = 2 if "page=2" in path else 1
        return {"data": [{"id": page * 10 + 1}, {"id": page * 10 + 2}], "totalMarketsCount": 4}


class LimitlessClientTests(unittest.TestCase):
    def test_lists_raw_active_markets_without_authentication(self) -> None:
        payload = StubClient().list_active_raw()
        self.assertEqual(payload["totalMarketsCount"], 4)
        self.assertEqual(len(payload["data"]), 2)

    def test_requests_a_specific_public_page(self) -> None:
        client = StubClient()
        payload = client.list_active_raw(page=2, sort_by="high_value")
        self.assertEqual(payload["data"][0]["id"], 21)
        self.assertIn("page=2", client.paths[0])
        self.assertIn("limit=25", client.paths[0])
        self.assertIn("sortBy=high_value", client.paths[0])

    def test_collects_multiple_public_pages(self) -> None:
        client = StubClient()
        rows = client.list_active_pages(max_pages=2, sort_by="high_value")
        self.assertEqual([row["id"] for row in rows], [11, 12, 21, 22])


if __name__ == "__main__":
    unittest.main()
