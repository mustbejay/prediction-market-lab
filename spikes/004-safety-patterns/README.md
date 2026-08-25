# Spike 004: Safety patterns from OpenAlgo family

## Goal

Port three safety patterns from `marketcalls/openalgo` and siblings into our venue-agnostic execution policy gate, before we ever wire up authenticated execution.

## What was borrowed

| Pattern | Origin | Our equivalent |
|---|---|---|
| Kill switch | AutoAgent uses `touch data/KILL` — every order tool refuses while it exists | `KillSwitch` — file on disk, active/inactive, no restart needed |
| Audit trail | TradingAgent writes each order twice (pre-broker, post-broker) to JSONL + SQLite | `AuditTrail` — double-write, append-only JSONL, queryable SQLite |
| RiskGuard | TradingAgent's deterministic pre-broker checks (kill switch, margin affordability, fat-finger, duplicate detection, min quantity) | `RiskGuard` — five layered checks, all deterministic, LLM can't bypass |

## Components

### KillSwitch

```python
kill = KillSwitch(path=Path("data/KILL"))
assert not kill.is_active
kill.activate()   # writes timestamp
assert kill.is_active
kill.deactivate()
```

### AuditTrail

```python
audit = AuditTrail()
audit.pre_broker(record)      # write BEFORE sending to broker
audit.post_broker(record)     # write AFTER broker response
rows = audit.query(venue="polymarket", status="FILLED")
audit.close()
```

Two writes per order (pre/post), plus a queryable SQLite index.

### RiskGuard

```python
risk = RiskGuard(kill_switch=kill)
result = risk.check(
    record=order_record,
    account_funds=10000.0,
    required_margin=500.0,
    last_traded_price=0.54,
)
# result.allowed == False, result.blocked_by == ('fat_finger',)
```

Five checks in order:
1. Kill switch active?
2. Margin affordability (% of funds)?
3. Fat-finger guard (price deviation from LTP)?
4. Duplicate intent within 10 seconds?
5. Minimum quantity?

## Run

```bash
rm -rf spikes/004-safety-patterns/audit  # clean state
python spikes/004-safety-patterns/spike.py
```

## Next steps

- Integrate into `src/prediction_lab/venues/policy.py` when we wire up authenticated execution.
- Add unit tests in `tests/test_safety_patterns.py`.
- Consider making `KillSwitch` a singleton accessible from the executor layer.
