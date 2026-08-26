#!/usr/bin/env python3
"""FastAPI server for prediction market dashboard with LIVE Polymarket CLOB API."""

import json
import sys
import asyncio
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Optional
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel


# ============================================================================
# CONFIGURATION
# ============================================================================

POLYMARKET_GAMMA = "https://gamma-api.polymarket.com"
POLYMARKET_CLOB = "https://clob.polymarket.com"
UA = "predictions-lab/0.1 (+scanner)"
DATA_DIR = Path(__file__).parent.parent / "data"


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class MarketSnapshot:
    condition_id: str
    question: str
    outcome: str
    price: float
    timestamp: datetime
    price_history: list[float] = field(default_factory=list)
    volume_24h: float = 0.0
    open_interest: float = 0.0
    token_id: str = ""


@dataclass
class Opportunity:
    strategy: str
    condition_id: str
    question: str
    confidence: float
    entry_price: float
    expected_edge: float
    reason: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    volume_24h: float = 0.0


@dataclass
class PaperPosition:
    position_id: str
    strategy: str
    side: str
    entry_price: float
    size: float
    entry_time: datetime
    condition_id: str
    question: str
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


@dataclass
class DashboardState:
    markets: dict[str, MarketSnapshot] = field(default_factory=dict)
    opportunities: list[Opportunity] = field(default_factory=list)
    positions: list[PaperPosition] = field(default_factory=list)
    pnl_history: list[float] = field(default_factory=list)
    account_balance: float = 10000.0
    last_scan: Optional[datetime] = None
    scan_count: int = 0
    error_count: int = 0
    live_prices_enabled: bool = False


# ============================================================================
# APP STATE
# ============================================================================

app = FastAPI(title="Prediction Market Lab")
state = DashboardState()
config = {"paper_size": 5.0, "max_positions": 3, "poll_interval": 30}


# ============================================================================
# API ENDPOINTS
# ============================================================================

class EnterPositionRequest(BaseModel):
    opportunity_id: str
    size: float = 5.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


class ClosePositionRequest(BaseModel):
    position_id: str
    exit_price: float


@app.get("/")
async def index():
    """Serve the dashboard HTML."""
    return HTMLResponse(content=HTML_TEMPLATE)


@app.get("/api/state")
async def get_state():
    """Get current dashboard state."""
    return {
        "markets": len(state.markets),
        "opportunities": [asdict(o) for o in state.opportunities[-20:]],
        "positions": [asdict(p) for p in state.positions],
        "pnl_history": state.pnl_history[-50:],
        "account_balance": state.account_balance,
        "last_scan": state.last_scan.isoformat() if state.last_scan else None,
        "scan_count": state.scan_count,
        "error_count": state.error_count,
        "live_prices_enabled": state.live_prices_enabled,
        "config": config,
    }


@app.post("/api/enter-position")
async def enter_position(req: EnterPositionRequest):
    """Enter a paper trading position."""
    opp = next((o for o in state.opportunities if o.condition_id == req.opportunity_id), None)
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    if len(state.positions) >= config["max_positions"]:
        raise HTTPException(status_code=400, detail="Max positions reached")

    # Determine side based on strategy
    if opp.strategy == "H7_high":
        side = "Up" if opp.entry_price < 0.55 else "Down"
    elif opp.strategy == "H2":
        side = "Up" if opp.entry_price >= 0.70 else "Down"
    elif opp.strategy == "H3":
        side = "Up"  # Momentum continuation
    else:
        side = "Up"

    position = PaperPosition(
        position_id=str(uuid.uuid4())[:8],
        strategy=opp.strategy,
        side=side,
        entry_price=opp.entry_price,
        size=req.size,
        entry_time=datetime.now(timezone.utc),
        condition_id=opp.condition_id,
        question=opp.question,
        stop_loss=req.stop_loss,
        take_profit=req.take_profit,
    )
    state.positions.append(position)
    return {"success": True, "position": asdict(position)}


@app.post("/api/close-position")
async def close_position(req: ClosePositionRequest):
    """Close a paper trading position."""
    position = next((p for p in state.positions if p.position_id == req.position_id), None)
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")

    # Calculate P&L
    if position.side == "Up":
        pnl = (req.exit_price - position.entry_price) * position.size
    else:
        pnl = (position.entry_price - req.exit_price) * position.size

    state.account_balance += position.size + pnl
    state.positions.remove(position)
    state.pnl_history.append(pnl)

    return {"success": True, "pnl": pnl, "balance": state.account_balance}


@app.post("/api/config")
async def update_config(new_config: dict):
    """Update scanner configuration."""
    config.update(new_config)
    return {"success": True, "config": config}


@app.get("/api/backtest")
async def get_backtest_results():
    """Return backtest results from historical data."""
    return {
        "H7_high": {"edge": 0.066, "win_rate": 0.67, "sample": 42, "description": "0.5 discontinuity"},
        "H2": {"edge": 0.022, "win_rate": 0.89, "sample": 132, "description": "Late favourite"},
        "H3": {"edge": 0.022, "win_rate": 0.86, "sample": 84, "description": "Momentum"},
    }


@app.get("/api/markets")
async def get_markets():
    """Get all tracked markets."""
    return [
        {
            "condition_id": k,
            "question": v.question,
            "price": v.price,
            "volume": v.volume_24h,
            "timestamp": v.timestamp.isoformat(),
            "token_id": v.token_id,
        }
        for k, v in list(state.markets.items())[-50:]
    ]


@app.get("/api/load-sample")
async def load_sample_data():
    """Load sample data from historical snapshots for demo."""
    snapshot_dirs = [
        Path("C:/Users/user/Downloads/prediction-lab/prediction_lab_backup_20260825/data/snapshots"),
        Path("data/snapshots"),
    ]
    
    snapshot_dir = None
    for d in snapshot_dirs:
        if d.exists():
            snapshot_dir = d
            break
    
    if not snapshot_dir:
        return {"error": "Sample data not found"}
    
    files = sorted(snapshot_dir.glob("limitless_*.json"))
    if not files:
        return {"error": "No snapshot files found"}
    
    with open(files[-1]) as f:
        data = json.load(f)
    
    markets = data.get("markets", [])
    loaded = 0
    for m in markets:
        cond_id = m.get("venue_market_id") or m.get("id", "")
        if not cond_id:
            continue
        
        buy = m.get("executable_buy_prices") or m.get("tradePrices", {}).get("buy", {}).get("market")
        if not buy or len(buy) < 2 or buy[0] is None or buy[1] is None:
            continue
        
        try:
            p_up = float(buy[0])
            p_dn = float(buy[1])
        except (TypeError, ValueError):
            continue
        
        state.markets[cond_id] = MarketSnapshot(
            condition_id=cond_id,
            question=m.get("title", "")[:60],
            outcome="Up" if p_up < p_dn else "Down",
            price=p_up,
            timestamp=datetime.now(timezone.utc),
            price_history=[p_up],
        )
        loaded += 1
        
        if 0.50 <= p_up < 0.60:
            state.opportunities.append(Opportunity(
                strategy="H7_high", condition_id=cond_id,
                question=m.get("title", "")[:60], confidence=0.8,
                entry_price=p_up, expected_edge=0.066,
                reason=f"p(Up)={p_up:.3f} in [0.5, 0.6)",
            ))
    
    state.opportunities = state.opportunities[-50:]
    return {"loaded": loaded, "total_markets": len(state.markets), "opportunities": len(state.opportunities)}


@app.get("/api/prices/{condition_id}")
async def get_price_history(condition_id: str):
    """Get price history for a market."""
    snap = state.markets.get(condition_id)
    if not snap:
        return {"error": "Market not found"}
    return {"prices": snap.price_history[-100:], "timestamps": [snap.timestamp.isoformat()]}


@app.get("/api/fetch-live")
async def fetch_live_prices():
    """Fetch live prices from Polymarket CLOB API and Kalshi."""
    fetched = 0
    errors = 0
    
    # Try Polymarket CLOB first
    markets_to_check = list(state.markets.items())[:50]
    
    for cond_id, snap in markets_to_check:
        try:
            url = f"{POLYMARKET_CLOB}/price?token_id={cond_id}&side=BUY"
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                if "price" in data:
                    p = float(data["price"])
                    if 0 < p < 1:
                        snap.price = p
                        snap.timestamp = datetime.now(timezone.utc)
                        snap.price_history.append(p)
                        snap.price_history = snap.price_history[-100:]
                        fetched += 1
                        
                        # Check for opportunities
                        if 0.50 <= p < 0.60:
                            opp = Opportunity(
                                strategy="H7_high", condition_id=cond_id,
                                question=snap.question, confidence=0.8,
                                entry_price=p, expected_edge=0.066,
                                reason=f"Live P: p={p:.3f}",
                            )
                            if not any(o.condition_id == cond_id and o.strategy == "H7_high" for o in state.opportunities):
                                state.opportunities.append(opp)
                                state.opportunities = state.opportunities[-50:]
                        
                        if p >= 0.70:
                            opp = Opportunity(
                                strategy="H2", condition_id=cond_id,
                                question=snap.question, confidence=0.7,
                                entry_price=p, expected_edge=0.022,
                                reason=f"Live P: Late fav p={p:.3f}",
                            )
                            if not any(o.condition_id == cond_id and o.strategy == "H2" for o in state.opportunities):
                                state.opportunities.append(opp)
        except:
            errors += 1
    
    # Try Kalshi as fallback
    try:
        from scripts.kalshi_client import fetch_kalshi_markets
        kalshi_markets = fetch_kalshi_markets()
        
        for km in kalshi_markets[:20]:
            # Create synthetic condition_id from ticker
            cond_id = f"kalshi_{km['ticker']}"
            
            # Check for opportunities
            if 0.50 <= km["price"] < 0.60:
                opp = Opportunity(
                    strategy="H7_high", condition_id=cond_id,
                    question=km["question"], confidence=0.7,
                    entry_price=km["price"], expected_edge=0.066,
                    reason=f"Kalshi: p={km['price']:.3f}",
                )
                state.opportunities.append(opp)
            
            if km["price"] >= 0.70:
                opp = Opportunity(
                    strategy="H2", condition_id=cond_id,
                    question=km["question"], confidence=0.7,
                    entry_price=km["price"], expected_edge=0.022,
                    reason=f"Kalshi: Late fav p={km['price']:.3f}",
                )
                state.opportunities.append(opp)
            
            # Add to markets
            state.markets[cond_id] = MarketSnapshot(
                condition_id=cond_id,
                question=km["question"],
                outcome="Up" if km["price"] < 0.5 else "Down",
                price=km["price"],
                timestamp=datetime.now(timezone.utc),
                price_history=[km["price"]],
                volume_24h=km["volume"],
            )
            fetched += 1
            
    except Exception as e:
        print(f"Kalshi fetch error: {e}", file=sys.stderr)
    
    state.live_prices_enabled = fetched > 0
    return {"fetched": fetched, "errors": errors, "total_markets": len(state.markets)}


@app.post("/api/enable-live")
async def enable_live_prices():
    """Enable live price fetching."""
    state.live_prices_enabled = True
    return {"success": True, "live_prices_enabled": state.live_prices_enabled}


@app.post("/api/disable-live")
async def disable_live_prices():
    """Disable live price fetching."""
    state.live_prices_enabled = False
    return {"success": True, "live_prices_enabled": state.live_prices_enabled}


# ============================================================================
# HTML TEMPLATE
# ============================================================================

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Prediction Market Lab</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--background);
            color: var(--foreground);
            min-height: 100vh;
        }
        :root {
            --background: #0a0a0a;
            --foreground: #e5e5e5;
            --muted: #737373;
            --border: #27272a;
            --card: #18181b;
            --accent: #3b82f6;
            --success: #22c55e;
            --warning: #f59e0b;
            --danger: #ef4444;
        }
        .container { max-width: 1600px; margin: 0 auto; padding: 20px; }
        header {
            display: flex; justify-content: space-between; align-items: center;
            padding: 20px 0; border-bottom: 1px solid var(--border); margin-bottom: 20px;
        }
        h1 { font-size: 24px; font-weight: 600; }
        .stats {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px; margin-bottom: 24px;
        }
        .stat-card {
            background: var(--card); border: 1px solid var(--border);
            border-radius: 8px; padding: 16px;
        }
        .stat-label { font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
        .stat-value { font-size: 28px; font-weight: 600; margin-top: 4px; }
        .stat-value.positive { color: var(--success); }
        .stat-value.negative { color: var(--danger); }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        @media (max-width: 1200px) { .grid { grid-template-columns: 1fr; } }
        .card {
            background: var(--card); border: 1px solid var(--border);
            border-radius: 8px; padding: 20px; margin-bottom: 20px;
        }
        .card-header {
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 16px;
        }
        .card-title { font-size: 16px; font-weight: 600; }
        .badge {
            display: inline-block; padding: 4px 8px; border-radius: 4px;
            font-size: 12px; font-weight: 500;
        }
        .badge-h7 { background: #3b82f6; color: white; }
        .badge-h2 { background: #22c55e; color: white; }
        .badge-h3 { background: #f59e0b; color: black; }
        .badge-live { background: var(--success); color: white; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid var(--border); }
        th { font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
        tr:hover { background: rgba(255,255,255,0.02); }
        .btn {
            display: inline-flex; align-items: center; gap: 6px;
            padding: 8px 16px; border: none; border-radius: 6px;
            font-size: 14px; cursor: pointer; transition: opacity 0.2s;
        }
        .btn:hover { opacity: 0.8; }
        .btn-primary { background: var(--accent); color: white; }
        .btn-success { background: var(--success); color: white; }
        .btn-danger { background: var(--danger); color: white; }
        .btn-sm { padding: 4px 12px; font-size: 12px; }
        .empty-state { text-align: center; padding: 40px; color: var(--muted); }
        .pulse { animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .live-dot { display: inline-block; width: 8px; height: 8px; background: var(--success); border-radius: 50%; margin-right: 8px; }
        .controls { display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; }
        .refresh-btn, .load-btn, .live-btn {
            background: none; border: 1px solid var(--border); color: var(--foreground);
            padding: 8px 16px; border-radius: 6px; cursor: pointer;
        }
        .refresh-btn:hover, .load-btn:hover, .live-btn:hover { background: var(--border); }
        .load-btn { background: var(--accent); color: white; border: none; }
        .load-btn:hover { opacity: 0.9; }
        .live-btn { background: var(--success); color: white; border: none; }
        .live-btn.active { background: var(--warning); }
        .live-btn:hover { opacity: 0.9; }
        .chart-container { position: relative; height: 300px; margin-top: 20px; }
        .modal {
            display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.8); z-index: 1000; align-items: center; justify-content: center;
        }
        .modal.active { display: flex; }
        .modal-content {
            background: var(--card); border: 1px solid var(--border);
            border-radius: 8px; padding: 24px; max-width: 400px; width: 90%;
        }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
        .modal-title { font-size: 18px; font-weight: 600; }
        .modal-close { background: none; border: none; color: var(--muted); font-size: 24px; cursor: pointer; }
        .form-group { margin-bottom: 16px; }
        .form-label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 4px; }
        .form-input {
            width: 100%; padding: 10px; background: var(--background);
            border: 1px solid var(--border); border-radius: 6px; color: var(--foreground);
        }
        .toast {
            position: fixed; bottom: 20px; right: 20px; background: var(--card);
            border: 1px solid var(--border); border-radius: 8px; padding: 16px;
            z-index: 2000; transform: translateY(100px); opacity: 0; transition: all 0.3s;
        }
        .toast.show { transform: translateY(0); opacity: 1; }
        .toast.success { border-color: var(--success); }
        .toast.error { border-color: var(--danger); }
        .status-badge {
            display: inline-block; padding: 4px 12px; border-radius: 4px;
            font-size: 12px; font-weight: 500; margin-left: 12px;
        }
        .status-live { background: var(--success); color: white; }
        .status-offline { background: var(--muted); color: white; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1><span class="live-dot pulse"></span>Prediction Market Lab</h1>
            <div style="display: flex; align-items: center; gap: 16px;">
                <span id="last-scan" style="color: var(--muted); font-size: 14px;"></span>
                <span id="live-status" class="status-badge status-offline">OFFLINE</span>
                <button class="refresh-btn" onclick="fetchState()">Refresh</button>
            </div>
        </header>

        <div class="controls">
            <button class="load-btn" onclick="loadSampleData()">Load Sample Data</button>
            <button class="live-btn" id="live-btn" onclick="toggleLivePrices()">Enable Live Prices</button>
            <button class="refresh-btn" onclick="fetchState()">Refresh State</button>
        </div>

        <div class="stats">
            <div class="stat-card">
                <div class="stat-label">Account Balance</div>
                <div class="stat-value" id="balance">$10,000.00</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Total P&L</div>
                <div class="stat-value" id="total-pnl">$0.00</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Markets Tracked</div>
                <div class="stat-value" id="markets-count">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Open Positions</div>
                <div class="stat-value" id="positions-count">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Scans Run</div>
                <div class="stat-value" id="scan-count">0</div>
            </div>
        </div>

        <div class="grid">
            <div class="card">
                <div class="card-header">
                    <span class="card-title">Live Opportunities</span>
                    <span id="opp-count" class="badge badge-h7">0</span>
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>Strategy</th>
                            <th>Market</th>
                            <th>Price</th>
                            <th>Edge</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody id="opportunities-table">
                        <tr><td colspan="5" class="empty-state">Loading...</td></tr>
                    </tbody>
                </table>
            </div>

            <div class="card">
                <div class="card-header">
                    <span class="card-title">Open Positions</span>
                    <span id="pos-count" class="badge badge-h2">0</span>
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>Strategy</th>
                            <th>Side</th>
                            <th>Entry</th>
                            <th>Size</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody id="positions-table">
                        <tr><td colspan="5" class="empty-state">No positions</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <div class="card" id="chart-card" style="display: none;">
            <div class="card-header">
                <span class="card-title" id="chart-title">Price History</span>
                <button class="refresh-btn btn-sm" onclick="closeChart()">Close</button>
            </div>
            <div class="chart-container">
                <canvas id="price-chart"></canvas>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <span class="card-title">Backtest Results</span>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Strategy</th>
                        <th>Description</th>
                        <th>Expected Edge</th>
                        <th>Win Rate</th>
                        <th>Sample</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody id="backtest-table"></tbody>
            </table>
        </div>
    </div>

    <!-- Enter Position Modal -->
    <div class="modal" id="enter-modal">
        <div class="modal-content">
            <div class="modal-header">
                <span class="modal-title">Enter Position</span>
                <button class="modal-close" onclick="closeModal('enter-modal')">&times;</button>
            </div>
            <div class="form-group">
                <label class="form-label">Position Size (shares)</label>
                <input type="number" class="form-input" id="enter-size" value="5" min="1" step="1">
            </div>
            <div class="form-group">
                <label class="form-label">Stop Loss (optional)</label>
                <input type="number" class="form-input" id="enter-stop" placeholder="e.g., 0.30" step="0.01">
            </div>
            <div class="form-group">
                <label class="form-label">Take Profit (optional)</label>
                <input type="number" class="form-input" id="enter-take" placeholder="e.g., 0.80" step="0.01">
            </div>
            <button class="btn btn-success" style="width: 100%;" onclick="confirmEnter()">Enter Position</button>
        </div>
    </div>

    <!-- Close Position Modal -->
    <div class="modal" id="close-modal">
        <div class="modal-content">
            <div class="modal-header">
                <span class="modal-title">Close Position</span>
                <button class="modal-close" onclick="closeModal('close-modal')">&times;</button>
            </div>
            <div class="form-group">
                <label class="form-label">Exit Price</label>
                <input type="number" class="form-input" id="close-price" placeholder="e.g., 0.65" step="0.01">
            </div>
            <button class="btn btn-danger" style="width: 100%;" onclick="confirmClose()">Close Position</button>
        </div>
    </div>

    <!-- Toast Notification -->
    <div class="toast" id="toast"></div>

    <script>
        const API = '/api';
        let refreshInterval;
        let currentOppId = null;
        let currentPosId = null;
        let chart = null;
        let liveEnabled = false;

        async function fetchState() {
            try {
                const resp = await fetch(API + '/state');
                const data = await resp.json();
                liveEnabled = data.live_prices_enabled;
                updateLiveStatus(liveEnabled);
                updateUI(data);
            } catch (e) {
                console.error('Fetch error:', e);
                showToast('Failed to fetch state', 'error');
            }
        }

        function updateLiveStatus(enabled) {
            const badge = document.getElementById('live-status');
            const btn = document.getElementById('live-btn');
            if (enabled) {
                badge.textContent = 'LIVE';
                badge.className = 'status-badge status-live';
                btn.textContent = 'Disable Live Prices';
                btn.classList.add('active');
            } else {
                badge.textContent = 'OFFLINE';
                badge.className = 'status-badge status-offline';
                btn.textContent = 'Enable Live Prices';
                btn.classList.remove('active');
            }
        }

        function updateUI(data) {
            // Update stats
            document.getElementById('balance').textContent = '$' + data.account_balance.toFixed(2);
            document.getElementById('markets-count').textContent = data.markets;
            document.getElementById('positions-count').textContent = data.positions.length;
            document.getElementById('scan-count').textContent = data.scan_count;
            
            const totalPnl = data.pnl_history.reduce((a, b) => a + b, 0);
            const pnlEl = document.getElementById('total-pnl');
            pnlEl.textContent = (totalPnl >= 0 ? '+' : '') + '$' + totalPnl.toFixed(2);
            pnlEl.className = 'stat-value ' + (totalPnl >= 0 ? 'positive' : 'negative');
            
            if (data.last_scan) {
                const d = new Date(data.last_scan);
                document.getElementById('last-scan').textContent = 'Last scan: ' + d.toLocaleTimeString();
            }

            // Update opportunities
            const oppTable = document.getElementById('opportunities-table');
            const oppCount = document.getElementById('opp-count');
            oppCount.textContent = data.opportunities.length;
            
            if (data.opportunities.length === 0) {
                oppTable.innerHTML = '<tr><td colspan="5" class="empty-state">No opportunities detected. Click "Load Sample Data" to see examples.</td></tr>';
            } else {
                oppTable.innerHTML = data.opportunities.map(opp => `
                    <tr>
                        <td><span class="badge badge-${opp.strategy.includes('H7') ? 'h7' : opp.strategy.includes('H2') ? 'h2' : 'h3'}">${opp.strategy}</span></td>
                        <td title="${opp.question}">${opp.question.substring(0, 35)}...</td>
                        <td>${opp.entry_price.toFixed(3)}</td>
                        <td class="${opp.expected_edge >= 0 ? 'positive' : 'negative'}">${opp.expected_edge >= 0 ? '+' : ''}${opp.expected_edge.toFixed(4)}</td>
                        <td>
                            <button class="btn btn-success btn-sm" onclick="openEnterModal('${opp.condition_id}')">Enter</button>
                            <button class="btn btn-sm" style="background:var(--muted);color:white;" onclick="showPriceChart('${opp.condition_id}', '${opp.question.replace(/'/g, "\\'")}')">Chart</button>
                        </td>
                    </tr>
                `).join('');
            }

            // Update positions
            const posTable = document.getElementById('positions-table');
            const posCount = document.getElementById('pos-count');
            posCount.textContent = data.positions.length;
            
            if (data.positions.length === 0) {
                posTable.innerHTML = '<tr><td colspan="5" class="empty-state">No open positions</td></tr>';
            } else {
                posTable.innerHTML = data.positions.map(pos => `
                    <tr>
                        <td><span class="badge badge-h2">${pos.strategy}</span></td>
                        <td>${pos.side}</td>
                        <td>${pos.entry_price.toFixed(3)}</td>
                        <td>${pos.size}</td>
                        <td><button class="btn btn-danger btn-sm" onclick="openCloseModal('${pos.position_id}')">Close</button></td>
                    </tr>
                `).join('');
            }

            // Update backtest table
            fetch(API + '/backtest').then(r => r.json()).then(results => {
                const tbody = document.getElementById('backtest-table');
                tbody.innerHTML = Object.entries(results).map(([strategy, data]) => {
                    const badgeClass = strategy.includes('H7') ? 'h7' : strategy.includes('H2') ? 'h2' : 'h3';
                    return `
                        <tr>
                            <td><span class="badge badge-${badgeClass}">${strategy}</span></td>
                            <td>${data.description}</td>
                            <td class="positive">+${(data.edge * 100).toFixed(2)}¢/share</td>
                            <td>${(data.win_rate * 100).toFixed(0)}%</td>
                            <td>${data.sample}</td>
                            <td><span class="badge badge-h2">Validated</span></td>
                        </tr>
                    `;
                }).join('');
            });
        }

        async function loadSampleData() {
            try {
                const resp = await fetch(API + '/load-sample');
                const data = await resp.json();
                if (data.error) {
                    showToast(data.error, 'error');
                } else {
                    showToast(`Loaded ${data.loaded} markets, ${data.opportunities} opportunities`, 'success');
                    fetchState();
                }
            } catch (e) {
                showToast('Error loading data', 'error');
            }
        }

        async function toggleLivePrices() {
            try {
                if (liveEnabled) {
                    await fetch(API + '/disable-live', { method: 'POST' });
                } else {
                    await fetch(API + '/enable-live', { method: 'POST' });
                    // Fetch live prices
                    const resp = await fetch(API + '/fetch-live');
                    const data = await resp.json();
                    showToast(`Fetched ${data.fetched} live prices, ${data.errors} errors`, data.errors === 0 ? 'success' : 'error');
                }
                fetchState();
            } catch (e) {
                showToast('Error toggling live prices', 'error');
            }
        }

        async function openEnterModal(conditionId) {
            currentOppId = conditionId;
            document.getElementById('enter-modal').classList.add('active');
        }

        async function confirmEnter() {
            const size = parseFloat(document.getElementById('enter-size').value);
            const stopLoss = document.getElementById('enter-stop').value ? parseFloat(document.getElementById('enter-stop').value) : null;
            const takeProfit = document.getElementById('enter-take').value ? parseFloat(document.getElementById('enter-take').value) : null;
            
            try {
                const resp = await fetch(API + '/enter-position', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({opportunity_id: currentOppId, size, stop_loss: stopLoss, take_profit: takeProfit})
                });
                const data = await resp.json();
                if (data.success) {
                    closeModal('enter-modal');
                    showToast('Position entered!', 'success');
                    fetchState();
                }
            } catch (e) {
                showToast('Error entering position', 'error');
            }
        }

        async function openCloseModal(positionId) {
            currentPosId = positionId;
            document.getElementById('close-modal').classList.add('active');
        }

        async function confirmClose() {
            const exitPrice = parseFloat(document.getElementById('close-price').value);
            if (isNaN(exitPrice)) {
                showToast('Please enter a valid price', 'error');
                return;
            }
            
            try {
                const resp = await fetch(API + '/close-position', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({position_id: currentPosId, exit_price: exitPrice})
                });
                const data = await resp.json();
                if (data.success) {
                    closeModal('close-modal');
                    showToast(`P&L: $${data.pnl.toFixed(2)}`, data.pnl >= 0 ? 'success' : 'error');
                    fetchState();
                }
            } catch (e) {
                showToast('Error closing position', 'error');
            }
        }

        async function showPriceChart(conditionId, question) {
            try {
                const resp = await fetch(API + '/prices/' + conditionId);
                const data = await resp.json();
                if (data.error) {
                    showToast(data.error, 'error');
                    return;
                }
                
                document.getElementById('chart-card').style.display = 'block';
                document.getElementById('chart-title').textContent = question;
                
                if (chart) chart.destroy();
                
                const ctx = document.getElementById('price-chart').getContext('2d');
                const labels = data.timestamps ? data.timestamps.map((_, i) => i) : data.prices.map((_, i) => i);
                
                chart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: 'Price',
                            data: data.prices,
                            borderColor: '#3b82f6',
                            backgroundColor: 'rgba(59, 130, 246, 0.1)',
                            fill: true,
                            tension: 0.4
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: {
                            x: { display: false },
                            y: { beginAtZero: true, max: 1 }
                        }
                    }
                });
                
                document.getElementById('chart-card').scrollIntoView({ behavior: 'smooth' });
            } catch (e) {
                showToast('Error loading chart', 'error');
            }
        }

        function closeChart() {
            document.getElementById('chart-card').style.display = 'none';
            if (chart) chart.destroy();
        }

        function closeModal(id) {
            document.getElementById(id).classList.remove('active');
        }

        function showToast(message, type = 'success') {
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.className = 'toast ' + type + ' show';
            setTimeout(() => toast.classList.remove('show'), 3000);
        }

        // Close modals on outside click
        window.onclick = function(event) {
            if (event.target.classList.contains('modal')) {
                event.target.classList.remove('active');
            }
        }

        // Start polling
        fetchState();
        refreshInterval = setInterval(fetchState, 30000);
    </script>
</body>
</html>"""


# ============================================================================
# BACKGROUND SCANNER TASK
# ============================================================================

async def scanner_task():
    """Background task that polls Polymarket CLOB API for live prices."""
    import time as time_module
    
    while True:
        try:
            if state.live_prices_enabled and state.scan_count % 10 == 0:  # Every 10 scans
                state.scan_count += 1
                state.last_scan = datetime.now(timezone.utc)
                
                # Fetch live prices for all tracked markets
                fetched = 0
                errors = 0
                
                for cond_id, snap in list(state.markets.items())[:50]:  # Limit to 50
                    try:
                        # Try CLOB API with condition_id as token_id
                        url = f"{POLYMARKET_CLOB}/price?token_id={cond_id}&side=BUY"
                        req = urllib.request.Request(url, headers={"User-Agent": UA})
                        with urllib.request.urlopen(req, timeout=5) as resp:
                            data = json.loads(resp.read().decode())
                            if "price" in data:
                                p = float(data["price"])
                                if 0 < p < 1:  # Valid price
                                    snap.price = p
                                    snap.timestamp = datetime.now(timezone.utc)
                                    snap.price_history.append(p)
                                    snap.price_history = snap.price_history[-100:]
                                    fetched += 1
                                    
                                    # Check for opportunities
                                    if 0.50 <= p < 0.60:
                                        opp = Opportunity(
                                            strategy="H7_high",
                                            condition_id=cond_id,
                                            question=snap.question,
                                            confidence=0.8,
                                            entry_price=p,
                                            expected_edge=0.066,
                                            reason=f"Live: p(Up)={p:.3f}",
                                        )
                                        if not any(o.condition_id == cond_id and o.strategy == "H7_high" for o in state.opportunities):
                                            state.opportunities.append(opp)
                                            state.opportunities = state.opportunities[-50:]
                                    
                                    if p >= 0.70:
                                        opp = Opportunity(
                                            strategy="H2",
                                            condition_id=cond_id,
                                            question=snap.question,
                                            confidence=0.7,
                                            entry_price=p,
                                            expected_edge=0.022,
                                            reason=f"Live: Late fav p(Up)={p:.3f}",
                                        )
                                        if not any(o.condition_id == cond_id and o.strategy == "H2" for o in state.opportunities):
                                            state.opportunities.append(opp)
                    
                    except Exception as e:
                        errors += 1
                
                if fetched > 0 or errors > 0:
                    print(f"[LIVE] Fetched: {fetched}, Errors: {errors}", file=sys.stderr)
        
        except Exception as e:
            print(f"Scanner error: {e}", file=sys.stderr)
        
        await asyncio.sleep(config["poll_interval"])


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    import threading
    
    # Start scanner in background thread
    def run_scanner():
        asyncio.run(scanner_task())
    
    scanner_thread = threading.Thread(target=run_scanner, daemon=True)
    scanner_thread.start()
    
    # Start FastAPI server
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
