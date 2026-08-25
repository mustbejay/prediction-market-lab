"""Tests for Spike 005: Trend Intel Command Center."""

import pytest
from datetime import datetime, timezone
from pathlib import Path
import json
import sys

# Add spike directory to path
spike_path = Path(__file__).parent.parent / "spikes" / "005-trend-intel"
sys.path.insert(0, str(spike_path))

from spike import (
    KillSwitch,
    detect_regime,
    score_market,
    InventoryMetrics,
    ScanRecord,
    AuditTrail,
)


class TestKillSwitch:
    def test_defaults_inactive(self, tmp_path: Path) -> None:
        kill = KillSwitch(tmp_path / "KILL")
        assert not kill.is_active

    def test_activate(self, tmp_path: Path) -> None:
        kill = KillSwitch(tmp_path / "KILL")
        kill.activate()
        assert kill.is_active

    def test_deactivate(self, tmp_path: Path) -> None:
        kill = KillSwitch(tmp_path / "KILL")
        kill.activate()
        kill.deactivate()
        assert not kill.is_active

    def test_check_raises_when_active(self, tmp_path: Path) -> None:
        kill = KillSwitch(tmp_path / "KILL")
        kill.activate()
        with pytest.raises(SystemExit):
            kill.check()

    def test_check_passes_when_inactive(self, tmp_path: Path) -> None:
        kill = KillSwitch(tmp_path / "KILL")
        kill.check()  # Should not raise


class TestDetectRegime:
    def test_chop_regime(self) -> None:
        markets = [
            InventoryMetrics(
                condition_id="test1",
                asset="btc",
                slug="btc-updown-15m-1234567890",
                up_quantity=100,
                down_quantity=90,
                up_vwap=0.55,
                down_vwap=0.50,
                paired_quantity=90,
                balance_ratio=0.9,
                pair_cost=1.05,
                locked_pair_pnl_before_fees=None,
                remainder_outcome="up",
                remainder_quantity=10,
                outcome_switches=5,
                fill_count=10,
            )
        ]
        regime = detect_regime(markets)
        assert regime["classification"] == "chop"
        assert regime["median_pair_cost"] == 1.05

    def test_trending_regime(self) -> None:
        markets = [
            InventoryMetrics(
                condition_id="test1",
                asset="btc",
                slug="btc-updown-15m-1234567890",
                up_quantity=100,
                down_quantity=100,
                up_vwap=0.45,
                down_vwap=0.45,
                paired_quantity=100,
                balance_ratio=1.0,
                pair_cost=0.90,
                locked_pair_pnl_before_fees=10.0,
                remainder_outcome=None,
                remainder_quantity=0,
                outcome_switches=10,
                fill_count=20,
            )
        ]
        regime = detect_regime(markets)
        assert regime["classification"] == "trending"

    def test_trending_strong(self) -> None:
        markets = [
            InventoryMetrics(
                condition_id="test1",
                asset="btc",
                slug="btc-updown-15m-1234567890",
                up_quantity=100,
                down_quantity=100,
                up_vwap=0.40,
                down_vwap=0.40,
                paired_quantity=100,
                balance_ratio=1.0,
                pair_cost=0.80,
                locked_pair_pnl_before_fees=20.0,
                remainder_outcome=None,
                remainder_quantity=0,
                outcome_switches=15,
                fill_count=20,
            )
        ]
        regime = detect_regime(markets)
        assert regime["classification"] == "trending_strong"

    def test_unknown_when_no_markets(self) -> None:
        regime = detect_regime([])
        assert regime["classification"] == "unknown"


class TestScoreMarket:
    def test_high_score_for_cheap_pair(self) -> None:
        metrics = InventoryMetrics(
            condition_id="test1",
            asset="btc",
            slug="test",
            up_quantity=100,
            down_quantity=100,
            up_vwap=0.45,
            down_vwap=0.45,
            paired_quantity=100,
            balance_ratio=1.0,
            pair_cost=0.90,
            locked_pair_pnl_before_fees=10.0,
            remainder_outcome=None,
            remainder_quantity=0,
            outcome_switches=10,
            fill_count=20,
        )
        regime = {"classification": "trending"}
        result = score_market(metrics, regime)
        assert result["score"] > 0.7
        assert result["recommendation"] == "watch"

    def test_low_score_for_expensive_pair(self) -> None:
        metrics = InventoryMetrics(
            condition_id="test1",
            asset="btc",
            slug="test",
            up_quantity=100,
            down_quantity=90,
            up_vwap=0.60,
            down_vwap=0.55,
            paired_quantity=90,
            balance_ratio=0.9,
            pair_cost=1.15,  # Expensive pair
            locked_pair_pnl_before_fees=None,
            remainder_outcome="up",
            remainder_quantity=10,
            outcome_switches=1,  # Low switches
            fill_count=5,  # Low volume
        )
        regime = {"classification": "chop"}
        result = score_market(metrics, regime)
        # Pair cost score should be 0, rest adds up
        assert result["score"] < 0.6
        # Recommendation depends on composite score thresholds
        assert result["recommendation"] in ("avoid", "consider")

    def test_no_data_returns_zero(self) -> None:
        metrics = InventoryMetrics(
            condition_id="test1",
            asset="btc",
            slug="test",
            up_quantity=0,
            down_quantity=0,
            up_vwap=None,
            down_vwap=None,
            paired_quantity=0,
            balance_ratio=0.0,
            pair_cost=None,
            locked_pair_pnl_before_fees=None,
            remainder_outcome=None,
            remainder_quantity=0,
            outcome_switches=0,
            fill_count=0,
        )
        regime = {"classification": "unknown"}
        result = score_market(metrics, regime)
        assert result["score"] == 0.0
        assert result["recommendation"] == "avoid"


class TestAuditTrail:
    def test_log_creates_file(self, tmp_path: Path) -> None:
        audit = AuditTrail(tmp_path / "audit.jsonl")
        record = ScanRecord(
            generated_at=datetime.now(timezone.utc).isoformat(),
            regime_classification="chop",
            market_count=10,
            markets_with_data=5,
            median_pair_cost=0.95,
            top_opportunity_count=2,
        )
        audit.log(record)
        log_file = tmp_path / "audit.jsonl"
        assert log_file.exists()
        content = log_file.read_text()
        assert "chop" in content
        assert "0.95" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
