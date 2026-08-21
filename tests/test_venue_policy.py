import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from prediction_lab.venues.policy import ExecutionPolicy, VenueCandidate


class ExecutionPolicyTests(unittest.TestCase):
    def test_execution_defaults_fail_closed(self) -> None:
        policy = ExecutionPolicy()
        self.assertFalse(policy.can_execute)
        self.assertIn("terms", policy.blockers)
        self.assertIn("jurisdiction", policy.blockers)
        self.assertIn("adapter", policy.blockers)
        self.assertIn("user", policy.blockers)

    def test_all_gates_must_be_explicitly_enabled(self) -> None:
        policy = ExecutionPolicy(
            terms_allow=True,
            jurisdiction_verified=True,
            adapter_tested=True,
            user_enabled=False,
        )
        self.assertFalse(policy.can_execute)
        self.assertEqual(policy.blockers, ("user",))

    def test_atomic_is_recorded_as_polymarket_access_layer(self) -> None:
        venue = VenueCandidate(
            venue_id="atomic-polymarket",
            operator="polymarket",
            role="wallet_frontend",
            chains=(137,),
            terms_url="https://docs.polymarket.com/api-reference/geoblock",
        )
        self.assertEqual(venue.operator, "polymarket")
        self.assertNotEqual(venue.venue_id, venue.operator)
        self.assertFalse(venue.execution_policy.can_execute)


if __name__ == "__main__":
    unittest.main()
