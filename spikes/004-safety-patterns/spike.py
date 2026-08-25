"""
Spike 004: Port kill switch + audit trail safety patterns from OpenAlgo family.

Borrowed from marketcalls/openalgo and siblings:
- Kill switch: touch a file to halt without restarting anything.
  AutoAgent uses data/KILL; every order tool refuses while it exists.
- Audit trail: write each order twice (before broker, after broker) to
  JSONL + SQLite so there is an immutable record of what happened and why.
- RiskGuard layer: deterministic checks after approval, before broker.

Goal: add these to our venue-agnostic execution policy gate so that when
we eventually wire up authenticated execution, the fail-closed safety is
in place from day one.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SPIKE_DIR = ROOT / "spikes" / "004-safety-patterns"


# ---------------------------------------------------------------------------
# Kill switch
# ---------------------------------------------------------------------------

class KillSwitch:
    """File-based emergency halt. No restart required."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or SPIKE_DIR / "KILL"

    @property
    def is_active(self) -> bool:
        return self._path.exists()

    def activate(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            f"killed_at={datetime.now(timezone.utc).isoformat()}\n",
            encoding="utf-8",
        )

    def deactivate(self) -> None:
        if self._path.exists():
            self._path.unlink()

    def __repr__(self) -> str:
        return f"KillSwitch({self._path}, active={self.is_active})"


# ---------------------------------------------------------------------------
# Audit trail (JSONL + SQLite)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OrderRecord:
    intent_id: str
    venue: str
    action: str  # BUY / SELL
    market_id: str
    outcome: str | None
    quantity: float
    price: float | None
    status: str  # PENDING_ENTRY / FILLED / REJECTED / HALTED
    reason: str | None
    timestamp_iso: str
    risk_guard_checks: dict[str, bool] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class AuditTrail:
    """Double-write audit: JSONL for append-only log, SQLite for queries."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._jsonl_path = SPIKE_DIR / "audit" / "orders.jsonl"
        self._db_path = db_path or SPIKE_DIR / "audit" / "orders.db"
        self._jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS orders (
                intent_id TEXT NOT NULL,
                venue TEXT NOT NULL,
                action TEXT NOT NULL,
                market_id TEXT NOT NULL,
                outcome TEXT,
                quantity REAL NOT NULL,
                price REAL,
                status TEXT NOT NULL,
                reason TEXT,
                timestamp_iso TEXT NOT NULL,
                risk_guard_checks TEXT,
                metadata TEXT
            )"""
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_status ON orders(status)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_venue ON orders(venue)"
        )
        self._conn.commit()

    def pre_broker(self, record: OrderRecord) -> None:
        """Write BEFORE sending to broker (PENDING_ENTRY)."""
        self._write(record, "PENDING_ENTRY")

    def post_broker(self, record: OrderRecord) -> None:
        """Write AFTER broker response (filled/rejected/failed)."""
        self._write(record, record.status)

    def _write(self, record: OrderRecord, status: str) -> None:
        record = OrderRecord(
            **{**asdict(record), "status": status},
        )
        line = json.dumps(asdict(record), default=str, separators=(",", ":"))
        with open(self._jsonl_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        self._conn.execute(
            """INSERT INTO orders
               (intent_id, venue, action, market_id, outcome, quantity,
                price, status, reason, timestamp_iso, risk_guard_checks, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.intent_id,
                record.venue,
                record.action,
                record.market_id,
                record.outcome,
                record.quantity,
                record.price,
                status,
                record.reason,
                record.timestamp_iso,
                json.dumps(record.risk_guard_checks, default=str),
                json.dumps(record.metadata, default=str),
            ),
        )
        self._conn.commit()

    def query(self, venue: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM orders WHERE 1=1"
        params: list[Any] = []
        if venue:
            sql += " AND venue = ?"
            params.append(venue)
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY timestamp_iso DESC"
        columns = [desc[0] for desc in self._conn.execute(sql, params).description]
        return [dict(zip(columns, row)) for row in self._conn.execute(sql, params).fetchall()]

    def close(self) -> None:
        self._conn.close()


# ---------------------------------------------------------------------------
# Risk guard (deterministic checks, after approval, before broker)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RiskGuardResult:
    allowed: bool
    blocked_by: tuple[str, ...] = ()
    notes: dict[str, str] = field(default_factory=dict)


class RiskGuard:
    """Deterministic pre-broker checks. Mirrors TradingAgent's RiskGuard."""

    def __init__(
        self,
        kill_switch: KillSwitch,
        max_order_pct_of_funds: float = 90.0,
        fat_finger_pct: float = 20.0,
        min_quantity: float = 0.01,
    ) -> None:
        self._kill = kill_switch
        self._max_pct = max_order_pct_of_funds
        self._fat_finger_pct = fat_finger_pct
        self._min_qty = min_quantity
        self._recent_intents: list[str] = []

    def check(
        self,
        record: OrderRecord,
        account_funds: float,
        required_margin: float,
        last_traded_price: float | None,
    ) -> RiskGuardResult:
        blockers: list[str] = []
        notes: dict[str, str] = {}

        # Layer 1: kill switch
        if self._kill.is_active:
            blockers.append("kill_switch")
            notes["kill_switch"] = f"active since {self._read_kill_time()}"

        # Layer 2: margin affordability
        if account_funds > 0 and required_margin > 0:
            pct = (required_margin / account_funds) * 100
            if pct > self._max_pct:
                blockers.append("margin_affordability")
                notes["margin_affordability"] = (
                    f"margin {required_margin:.2f} exceeds {self._max_pct}% "
                    f"of funds ({account_funds:.2f})"
                )

        # Layer 3: fat-finger guard
        if last_traded_price and record.price:
            deviation = abs(record.price - last_traded_price) / last_traded_price * 100
            if deviation > self._fat_finger_pct:
                blockers.append("fat_finger")
                notes["fat_finger"] = (
                    f"price {record.price} deviates {deviation:.1f}% "
                    f"from LTP {last_traded_price}"
                )

        # Layer 4: duplicate within window
        now = datetime.fromisoformat(record.timestamp_iso).timestamp()
        recent = [t for t in self._recent_intents if now - t < 10]
        if record.intent_id in recent:
            blockers.append("duplicate")
            notes["duplicate"] = "same intent_id within 10 seconds"
        self._recent_intents = recent + [now]

        # Layer 5: minimum quantity
        if record.quantity < self._min_qty:
            blockers.append("min_quantity")
            notes["min_quantity"] = f"{record.quantity} < {self._min_qty}"

        return RiskGuardResult(
            allowed=len(blockers) == 0,
            blocked_by=tuple(blockers),
            notes=notes,
        )

    def _read_kill_time(self) -> str:
        try:
            return (
                SPIKE_DIR / "KILL"
            ).read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return "unknown"


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def demo() -> None:
    print("=" * 60)
    print("Spike 004: Kill switch + audit trail + risk guard")
    print("=" * 60)

    kill = KillSwitch()
    audit = AuditTrail()
    risk = RiskGuard(kill)

    # --- Demo 1: kill switch ---
    print("\n--- Kill switch ---")
    print(f"initial: {kill}")
    kill.activate()
    print(f"after activate: {kill}")
    assert kill.is_active
    kill.deactivate()
    print(f"after deactivate: {kill}")
    assert not kill.is_active

    # --- Demo 2: audit trail ---
    print("\n--- Audit trail ---")
    record = OrderRecord(
        intent_id="test-001",
        venue="polymarket",
        action="BUY",
        market_id="abc123",
        outcome="Yes",
        quantity=100.0,
        price=0.55,
        status="PENDING_ENTRY",
        reason=None,
        timestamp_iso=datetime.now(timezone.utc).isoformat(),
        risk_guard_checks={"kill": True, "margin": True, "fat_finger": True},
    )
    audit.pre_broker(record)

    # Simulate fill
    record_filled = OrderRecord(
        intent_id="test-001",
        venue="polymarket",
        action="BUY",
        market_id="abc123",
        outcome="Yes",
        quantity=100.0,
        price=0.55,
        status="FILLED",
        reason="matched",
        timestamp_iso=datetime.now(timezone.utc).isoformat(),
        risk_guard_checks={"kill": True, "margin": True, "fat_finger": True},
    )
    audit.post_broker(record_filled)

    rows = audit.query(venue="polymarket")
    print(f"queried {len(rows)} rows")
    assert len(rows) == 2

    # --- Demo 3: risk guard ---
    print("\n--- Risk guard ---")
    kill.activate()
    result = risk.check(record, account_funds=10000.0, required_margin=500.0, last_traded_price=0.54)
    print(f"with kill active: allowed={result.allowed}, blocked_by={result.blocked_by}")
    assert not result.allowed
    assert "kill_switch" in result.blocked_by

    kill.deactivate()
    result = risk.check(record, account_funds=10000.0, required_margin=500.0, last_traded_price=0.54)
    print(f"normal check: allowed={result.allowed}, blocked_by={result.blocked_by}")
    assert result.allowed

    # Fat finger
    bad_record = OrderRecord(
        intent_id="fat-finger-test",
        venue="polymarket",
        action="BUY",
        market_id="abc123",
        outcome="Yes",
        quantity=100.0,
        price=0.70,  # >20% from 0.54
        status="PENDING_ENTRY",
        reason=None,
        timestamp_iso=datetime.now(timezone.utc).isoformat(),
        risk_guard_checks={"kill": True, "margin": True, "fat_finger": True},
    )
    result = risk.check(bad_record, account_funds=10000.0, required_margin=500.0, last_traded_price=0.54)
    print(f"fat finger: allowed={result.allowed}, blocked_by={result.blocked_by}")
    assert not result.allowed
    assert "fat_finger" in result.blocked_by

    audit.close()
    print("\nAll assertions passed.")


if __name__ == "__main__":
    demo()
