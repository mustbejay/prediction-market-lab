import unittest

from reconstruct import Fill, reconstruct


class ReconstructTests(unittest.TestCase):
    def test_directional_core_with_hedge(self) -> None:
        result = reconstruct(
            [
                Fill("m", "2026-08-01T00:00:01Z", "Up", 0.40, 250),
                Fill("m", "2026-08-01T00:02:00Z", "Down", 0.41, 145),
            ]
        )
        self.assertEqual(result.paired_quantity, 145)
        self.assertAlmostEqual(result.balance_ratio, 0.58)
        self.assertEqual(result.remainder_outcome, "up")
        self.assertEqual(result.remainder_quantity, 105)
        self.assertAlmostEqual(result.pair_cost or 0, 0.81)
        self.assertAlmostEqual(result.locked_pair_pnl_before_fees or 0, 27.55)
        self.assertEqual(result.outcome_switches, 1)

    def test_balanced_temporal_pair(self) -> None:
        result = reconstruct(
            [
                Fill("m", "2026-08-01T00:00:01Z", "Up", 0.44, 50),
                Fill("m", "2026-08-01T00:01:01Z", "Down", 0.53, 50),
            ]
        )
        self.assertEqual(result.balance_ratio, 1)
        self.assertIsNone(result.remainder_outcome)
        self.assertAlmostEqual(result.pair_cost or 0, 0.97)
        self.assertAlmostEqual(result.locked_pair_pnl_before_fees or 0, 1.5)

    def test_rejects_mixed_markets(self) -> None:
        with self.assertRaisesRegex(ValueError, "one market"):
            reconstruct(
                [
                    Fill("a", "1", "Up", 0.5, 1),
                    Fill("b", "2", "Down", 0.5, 1),
                ]
            )

    def test_rejects_invalid_fill(self) -> None:
        with self.assertRaisesRegex(ValueError, "outside"):
            reconstruct([Fill("m", "1", "Up", 1.1, 1)])


if __name__ == "__main__":
    unittest.main()
