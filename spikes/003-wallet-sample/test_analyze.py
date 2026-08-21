import unittest

from analyze import analyze, market_window, trade_key


class WalletAnalysisTests(unittest.TestCase):
    def test_market_window(self) -> None:
        self.assertEqual(market_window("btc-updown-5m-1000"), (1000, 1300))
        self.assertEqual(market_window("eth-updown-15m-1000"), (1000, 1900))
        self.assertIsNone(market_window("other-market"))

    def test_trade_key_keeps_distinct_fills(self) -> None:
        base = {
            "transactionHash": "0x1",
            "asset": "a",
            "timestamp": 1,
            "side": "BUY",
            "price": 0.4,
            "size": 5,
        }
        changed = dict(base, size=6)
        self.assertNotEqual(trade_key(base), trade_key(changed))

    def test_complete_market_stats(self) -> None:
        rows = [
            {
                "conditionId": "m",
                "transactionHash": "1",
                "asset": "up",
                "timestamp": 1010,
                "side": "BUY",
                "price": 0.4,
                "size": 10,
                "outcome": "Up",
                "title": "BTC Up or Down",
                "slug": "btc-updown-5m-1000",
            },
            {
                "conditionId": "m",
                "transactionHash": "2",
                "asset": "down",
                "timestamp": 1200,
                "side": "BUY",
                "price": 0.5,
                "size": 10,
                "outcome": "Down",
                "title": "BTC Up or Down",
                "slug": "btc-updown-5m-1000",
            },
            {
                "conditionId": "boundary",
                "transactionHash": "3",
                "asset": "up2",
                "timestamp": 900,
                "side": "BUY",
                "price": 0.5,
                "size": 1,
                "outcome": "Up",
                "title": "BTC Up or Down",
                "slug": "btc-updown-5m-800",
            },
            {
                "conditionId": "boundary2",
                "transactionHash": "4",
                "asset": "up3",
                "timestamp": 1400,
                "side": "BUY",
                "price": 0.5,
                "size": 1,
                "outcome": "Up",
                "title": "BTC Up or Down",
                "slug": "btc-updown-5m-1400",
            },
        ]
        report = analyze("0xabc", rows)
        complete = report["complete_up_down_stats"]
        self.assertEqual(complete["market_count"], 1)
        self.assertEqual(complete["two_sided_share"], 1)
        self.assertAlmostEqual(complete["median_pair_cost_two_sided"], 0.9)


if __name__ == "__main__":
    unittest.main()
