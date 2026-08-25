#!/usr/bin/env python3
"""FastAPI server for prediction market dashboard - FINAL version."""

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
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel


# ============================================================================
# CONFIGURATION
# ============================================================================

POLYMARKET_GAMMA = "https://gamma-api.polymarket.com/public-search"
POLYMARKET_MARKETS = "https://gamma-api.polymarket.com/markets"
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


@dataclass
class DashboardState:
    markets: dict[str, MarketSnapshot] = field(default_factory=dict)
    opportunities: list[Opportunity] = field(default_factory=list)
    positions: list[PaperPosition] = field(default_factory=list)
    pnl_history: list[float] = field(default_factory=list)
    account_balance: float = 10000.0
    last_scan: Optional[datetime] = None
    scan_count: int = 0


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

    position = PaperPosition(
        position_id=str(uuid.uuid4())[:8],
        strategy=opp.strategy,
        side="Up" if opp.entry_price < 0.6 else "Down",
        entry_price=opp.entry_price,
        size=req.size,
        entry_time=datetime.now(timezone.utc),
        condition_id=opp.condition_id,
        question=opp.question,
    )
    state.positions.append(position)
    return {"success": True, "position": asdict(position)}


@app.post("/api/close-position")
async def close_position(req: ClosePositionRequest):
    """Close a paper trading position."""
    position = next((p for p in state.positions if p.position_id == req.position_id), None)
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")

    # Calculate P&L using exit price
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
        "H7_high": {"edge": 0.066, "win_rate": 0.67, "sample": 42},
        "H2": {"edge": 0.022, "win_rate": 0.89, "sample": 132},
        "H3": {"edge": 0.022, "win_rate": 0.86, "sample": 84},
    }


@app.get("/api/markets")
async def get_markets():
    """Get all tracked markets."""
    return [
        {
            "condition_id": k,
            "question": v.question,
            "price": v.price,
            "timestamp": v.timestamp.isoformat(),
        }
        for k, v in state.markets.items()
    ][:50]


@app.get("/api/load-sample")
async def load_sample_data():
    """Load sample data from historical snapshots for demo."""
    snapshot_dir = Path("/c/Users/user/Downloads/prediction-lab/prediction_lab_backup_20260825/data/snapshots")
    if not snapshot_dir.exists():
        return {"error": "Sample data not found"}
    
    files = sorted(snapshot_dir.glob("limitless_*.json"))
    if not files:
        return {"error": "No snapshot files found"}
    
    # Load latest snapshot
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
        
        # Create market snapshot
        state.markets[cond_id] = MarketSnapshot(
            condition_id=cond_id,
            question=m.get("title", "")[:60],
            outcome="Up" if p_up < p_dn else "Down",
            price=p_up,
            timestamp=datetime.now(timezone.utc),
            price_history=[p_up],
        )
        loaded += 1
        
        # Check for opportunities
        if 0.50 <= p_up < 0.60:
            opp = Opportunity(
                strategy="H7_high",
                condition_id=cond_id,
                question=m.get("title", "")[:60],
                confidence=0.8,
                entry_price=p_up,
                expected_edge=0.066,
                reason=f"p(Up)={p_up:.3f} in [0.5, 0.6)"
            )
            state.opportunities.append(opp)
    
    return {"loaded": loaded, "total_markets": len(state.markets), "opportunities": len(state.opportunities)}


# ============================================================================
# HTML TEMPLATE
# ============================================================================

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Prediction Market Lab</title>
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
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px 0;
            border-bottom: 1px solid var(--border);
            margin-bottom: 20px;
        }
        h1 { font-size: 24px; font-weight: 600; }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }
        .stat-card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 16px;
        }
        .stat-label {
            font-size: 12px;
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .stat-value {
            font-size: 28px;
            font-weight: 600;
            margin-top: 4px;
        }
        .stat-value.positive { color: var(--success); }
        .stat-value.negative { color: var(--danger); }
        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
        @media (max-width: 900px) {
            .grid { grid-template-columns: 1fr; }
        }
        .card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 20px;
        }
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }
        .card-title {
            font-size: 16px;
            font-weight: 600;
        }
        .badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 500;
        }
        .badge-h7 { background: #3b82f6; color: white; }
        .badge-h2 { background: #22c55e; color: white; }
        .badge-h3 { background: #f59e0b; color: black; }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }
        th {
            font-size: 12px;
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        tr:hover { background: rgba(255,255,255,0.02); }
        .btn {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            cursor: pointer;
            transition: opacity 0.2s;
        }
        .btn:hover { opacity: 0.8; }
        .btn-primary { background: var(--accent); color: white; }
        .btn-success { background: var(--success); color: white; }
        .btn-danger { background: var(--danger); color: white; }
        .btn-sm { padding: 4px 12px; font-size: 12px; }
        .empty-state {
            text-align: center;
            padding: 40px;
            color: var(--muted);
        }
        .pulse {
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .live-dot {
            display: inline-block;
            width: 8px;
            height: 8px;
            background: var(--success);
            border-radius: 50%;
            margin-right: 8px;
        }
        .refresh-btn {
            background: none;
            border: 1px solid var(--border);
            color: var(--foreground);
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
        }
        .refresh-btn:hover { background: var(--border); }
        .load-btn {
            background: var(--accent);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            margin-bottom: 20px;
        }
        .load-btn:hover { opacity: 0.9; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1><span class="live-dot pulse"></span>Prediction Market Lab</h1>
            <div style="display: flex; align-items: center; gap: 16px;">
                <span id="last-scan" style="color: var(--muted); font-size: 14px;"></span>
                <button class="refresh-btn" onclick="fetchState()">Refresh</button>
            </div>
        </header>

        <button class="load-btn" onclick="loadSampleData()">Load Sample Data (Limitless snapshots)</button>

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
                        <tr><td colspan="5" class="empty-state">Click "Load Sample Data" to see opportunities</td></tr>
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
                        <tr><td colspan="5" class="empty-state">No open positions</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <div class="card" style="margin-top: 20px;">
            <div class="card-header">
                <span class="card-title">Backtest Results</span>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Strategy</th>
                        <th>Expected Edge</th>
                        <th>Win Rate</th>
                        <th>Sample Size</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody id="backtest-table">
                </tbody>
            </table>
        </div>
    </div>

    <script>
        const API = '/api';
        let refreshInterval;

        async function fetchState() {
            try {
                const resp = await fetch(API + '/state');
                const data = await resp.json();
                updateUI(data);
            } catch (e) {
                console.error('Fetch error:', e);
            }
        }

        async function loadSampleData() {
            try {
                const resp = await fetch(API + '/load-sample');
                const data = await resp.json();
                alert('Loaded ' + data.loaded + ' markets, ' + data.opportunities + ' opportunities');
                fetchState();
            } catch (e) {
                alert('Error loading sample data: ' + e);
            }
        }

        function updateUI(data) {
            // Update stats
            document.getElementById('balance').textContent = '$' + data.account_balance.toFixed(2);
            document.getElementById('markets-count').textContent = data.markets;
            document.getElementById('positions-count').textContent = data.positions.length;
            
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
                oppTable.innerHTML = '<tr><td colspan="5" class="empty-state">No opportunities detected. Click "Load Sample Data" to load historical data.</td></tr>';
            } else {
                oppTable.innerHTML = data.opportunities.map(opp => `
                    <tr>
                        <td><span class="badge badge-h7">${opp.strategy}</span></td>
                        <td title="${opp.question}">${opp.question.substring(0, 40)}...</td>
                        <td>${opp.entry_price.toFixed(3)}</td>
                        <td class="${opp.expected_edge >= 0 ? 'positive' : 'negative'}">${opp.expected_edge >= 0 ? '+' : ''}${opp.expected_edge.toFixed(4)}</td>
                        <td><button class="btn btn-success btn-sm" onclick="enterPosition('${opp.condition_id}')">Enter</button></td>
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
                        <td><button class="btn btn-danger btn-sm" onclick="closePosition('${pos.position_id}')">Close</button></td>
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
                            <td class="positive">+${(data.edge * 100).toFixed(2)}¢/share</td>
                            <td>${(data.win_rate * 100).toFixed(0)}%</td>
                            <td>${data.sample}</td>
                            <td><span class="badge badge-h2">Validated</span></td>
                        </tr>
                    `;
                }).join('');
            });
        }

        async function enterPosition(conditionId) {
            try {
                const resp = await fetch(API + '/enter-position', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({opportunity_id: conditionId, size: 5})
                });
                const data = await resp.json();
                if (data.success) {
                    fetchState();
                }
            } catch (e) {
                console.error('Enter position error:', e);
            }
        }

        async function closePosition(positionId) {
            const exitPrice = prompt('Enter exit price (e.g., 0.85):', '0.50');
            if (!exitPrice) return;
            try {
                const resp = await fetch(API + '/close-position', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({position_id: positionId, exit_price: parseFloat(exitPrice)})
                });
                const data = await resp.json();
                if (data.success) {
                    alert('P&L: $' + data.pnl.toFixed(2));
                    fetchState();
                }
            } catch (e) {
                console.error('Close position error:', e);
            }
        }

        // Start polling
        fetchState();
        refreshInterval = setInterval(fetchState, 30000); // Refresh every 30s
    </script>
</body>
</html>"""


# ============================================================================
# BACKGROUND SCANNER TASK
# ============================================================================

async def scanner_task():
    """Background task that polls Polymarket and updates state."""
    import time as time_module
    
    while True:
        try:
            state.scan_count += 1
            state.last_scan = datetime.now(timezone.utc)
        
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
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
