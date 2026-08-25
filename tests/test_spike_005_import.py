"""Test that import works correctly."""
import sys
from pathlib import Path

# Add spike directory to path
spike_path = Path(__file__).parent.parent / "spikes" / "005-trend-intel"
sys.path.insert(0, str(spike_path))

from spike import (
    KillSwitch,
    detect_regime,
    score_market,
    InventoryMetrics,
    discover_updown_markets,
)


def test_imports() -> None:
    """Verify all key classes and functions are importable."""
    assert KillSwitch is not None
    assert detect_regime is not None
    assert score_market is not None
    assert InventoryMetrics is not None
    assert discover_updown_markets is not None


def test_inventory_metrics_creation() -> None:
    """Test creating InventoryMetrics."""
    metrics = InventoryMetrics(
        condition_id="test1",
        asset="btc",
        slug="test",
        up_quantity=100,
        down_quantity=100,
        up_vwap=0.5,
        down_vwap=0.45,
        paired_quantity=100,
        balance_ratio=1.0,
        pair_cost=0.95,
        locked_pair_pnl_before_fees=5.0,
        remainder_outcome=None,
        remainder_quantity=0,
        outcome_switches=5,
        fill_count=10,
    )
    assert metrics.condition_id == "test1"
    assert metrics.pair_cost == 0.95
    assert metrics.balance_ratio == 1.0
