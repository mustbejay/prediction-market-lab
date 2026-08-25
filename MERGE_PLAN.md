# Merge Plan: prediction-market-lab (local/spikes) → Predictions-Lab (tablet/core)

## Current State

| Repo | Purpose | Structure | Tests | Status |
|------|---------|-----------|-------|--------|
| `mustbejay/Predictions-Lab` (tablet) | Core venue-agnostic library | Clean abstractions, TDD | 8 passing | Production-ready scaffold |
| `prediction-market-lab` (local/desktop) | Research & spike exploration | 5 spikes, 27 tests | 27 passing | Experimental |

## Merge Strategy

**Port, don't copy.** The tablet repo is the canonical codebase. Local spikes are validation experiments. After merging, local repo can be archived or repurposed as a scratch workspace.

---

## Phase 1: Scaffold Integration (1 day)

### 1.1 Add analysis/ module to tablet

```
src/prediction_lab/
├── __init__.py
├── venues/
│   ├── __init__.py
│   ├── model.py           # Already exists
│   ├── limitless.py       # Already exists
│   ├── policy.py          # Already exists
│   └── polymarket.py      # NEW: Polymarket CLOB/Gamma API adapter
├── analysis/              # NEW: Intelligence layer (from spikes)
│   ├── __init__.py
│   ├── discovery.py       # From spike 005: market discovery
│   ├── inventory.py       # From spike 002: pair cost, balance ratio
│   ├── regime.py          # From spike 005: chop/trending detection
│   ├── scoring.py         # From spike 005: opportunity scoring
│   └── command_center.py  # Orchestrator (spike 005 main)
└── safety/                # From spike 004
    ├── __init__.py
    ├── kill_switch.py
    └── audit_trail.py
```

### 1.2 Port spike code

| Spike | What to port | Notes |
|-------|--------------|-------|
| 001 | Polymarket Gamma API client | Extract from spike, add to `polymarket.py` |
| 002 | Inventory reconstruction | Already in spike 005, move to `analysis/inventory.py` |
| 004 | KillSwitch + AuditTrail | Move to `safety/` module |
| 005 | Command center orchestration | Rebuild using Phase 1 modules |

---

## Phase 2: Unified Tests (1 day)

### 2.1 Convert pytest → unittest

Tablet uses unittest. Local uses pytest. Standardize on unittest for consistency.

### 2.2 Add Polymarket adapter tests

```python
# tests/test_polymarket_adapter.py
class TestPolymarketClient(unittest.TestCase):
    def test_discover_updown_markets(self):
        # Test discovery logic
        pass
    
    def test_filter_by_timeframe(self):
        # Test slug pattern matching
        pass
```

### 2.3 Add analysis module tests

```python
# tests/test_analysis_inventory.py
class TestInventoryReconstruction(unittest.TestCase):
    def test_pair_cost_calculation(self):
        pass
    
    def test_balance_ratio_edge_cases(self):
        pass

# tests/test_analysis_regime.py
class TestRegimeDetection(unittest.TestCase):
    def test_chop_regime_high_pair_cost(self):
        pass
    
    def test_trending_regime_low_pair_cost(self):
        pass
```

**Target:** 25+ tests (up from 8)

---

## Phase 3: Scripts & CLI (0.5 days)

### 3.1 Port spike scripts

| Local Script | Tablet Location |
|--------------|-----------------|
| `spikes/005-trend-intel/spike.py` | `scripts/trend_intel.py` |
| `spikes/004-safety-patterns/spike.py` | `scripts/check_kill_switch.py` |
| `spikes/001-public-market-data/main.py` | `scripts/fetch_markets.py` |

### 3.2 Add requirements.txt / pyproject.toml

```toml
[project]
name = "prediction-lab"
version = "0.2.0"
dependencies = []  # stdlib only for now

[project.optional-dependencies]
dev = ["pytest", "pytest-asyncio"]
polymarket = []  # Will add when we need auth
```

---

## Phase 4: Documentation (0.5 days)

### 4.1 Update README

Add sections for:
- Analysis module usage
- Polymarket adapter
- Command center workflow
- Safety patterns (kill switch, audit trail)

### 4.2 Add architecture diagram

```
User → Command Center → Market Discovery
                      → Inventory Reconstruction  
                      → Regime Detection
                      → Opportunity Scoring
                      ↓
                  Execution Policy (4 gates)
                      ↓
                  Venues (Limitless, Polymarket, ...)
```

---

## What Stays Local

| Item | Reason |
|------|--------|
| `spikes/001-003/` | Research artifacts, not production code |
| `bot-research.txt` | Reference material, move to `docs/research/` |
| `scan-history.jsonl` | Runtime data, not needed in repo |

---

## Timeline

| Phase | Effort | PRs |
|-------|--------|-----|
| 1. Scaffold | 4h | 1 (structure) |
| 2. Tests | 4h | 1 (test port) |
| 3. Scripts | 2h | 1 (scripts) |
| 4. Docs | 2h | 1 (README + diagram) |

**Total: ~2 days of focused work**

---

## Open Questions

1. **Which repo is canonical?** Tablet (`mustbejay/Predictions-Lab`) or local?
   - Recommendation: Tablet is canonical (cleaner structure, more commits)
   
2. **Polymarket auth?** Spike 005 is read-only. Do we need authenticated access for execution?
   - Recommendation: Keep read-only for now, add auth when execution is enabled

3. **Test framework?** unittest vs pytest?
   - Recommendation: unittest (matches tablet convention)

---

## Next Actions

- [ ] Create branch `merge-spike-intelligence` on tablet repo
- [ ] Scaffold `analysis/` and `safety/` directories
- [ ] Port Limitless + Polymarket adapters
- [ ] Port spike 005 logic into analysis modules
- [ ] Port spike 004 safety patterns
- [ ] Add unified test suite
- [ ] Update README
- [ ] Merge to main
