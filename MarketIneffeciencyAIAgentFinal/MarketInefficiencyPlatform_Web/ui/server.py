from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from replit_scheduler import start_scheduler
from scheduler import schedule_agent, remove_agent, get_schedules
from fastapi.responses import FileResponse
import time
from db.database import add_finding, get_recent_findings
import json
import os
from datetime import datetime

app = FastAPI()
START = time.time()

# Get the directory where this server.py file is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# In-memory storage for findings (in production, use a database)
# FINDINGS_STORE = [
    {
        "id": 1,
        "title": "Spread Arbitrage Opportunity",
        "description": "BTC-USD spread detected: 0.15% difference between exchanges",
        "severity": "high",
        "agent": "SpreadScannerAgent",
        "timestamp": "2 minutes ago",
        "created_at": datetime.now().isoformat()
    },
    {
        "id": 2,
        "title": "Volume Momentum Signal",
        "description": "Unusual volume spike in AAPL (+340% above average)",
        "severity": "medium",
        "agent": "MomentumVolumeAgent",
        "timestamp": "5 minutes ago",
        "created_at": datetime.now().isoformat()
    },
    {
        "id": 3,
        "title": "Portfolio Risk Alert",
        "description": "Correlation risk elevated in tech sector positions",
        "severity": "low",
        "agent": "PortfolioRiskAgent",
        "timestamp": "8 minutes ago",
        "created_at": datetime.now().isoformat()
    }
]

@app.get("/")
def root():
    html_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    else:
        return {
            "error": "Dashboard file not found",
            "debug": {
                "current_working_directory": os.getcwd(),
                "looking_for_path": html_path,
                "base_dir": BASE_DIR,
                "static_dir": STATIC_DIR,
                "static_dir_exists": os.path.exists(STATIC_DIR),
                "files_in_static": os.listdir(STATIC_DIR) if os.path.exists(STATIC_DIR) else []
            }
        }

@app.get("/status")
def status():
    return {
        "app": "Market Inefficiency Platform",
        "status": "running",
        "mode": "realtime",
        "uptime_seconds": int(time.time() - START)
    }

@app.get("/dashboard")
def dashboard():
    html_path = os.path.join(STATIC_DIR, "index.html")

    if os.path.exists(html_path):
        return FileResponse(html_path)
    else:
        # If file doesn't exist, return debug info
        cwd = os.getcwd()
        return {
            "error": "Dashboard file not found",
            "debug": {
                "current_working_directory": cwd,
                "looking_for_path": html_path,
                "base_dir": BASE_DIR,
                "static_dir": STATIC_DIR,
                "static_dir_exists": os.path.exists(STATIC_DIR),
                "files_in_static": os.listdir(STATIC_DIR) if os.path.exists(STATIC_DIR) else []
            }
        }

@app.get("/agents")
def agents():
    return {"enabled_agents": ["SpreadScannerAgent", "MomentumVolumeAgent", "PortfolioRiskAgent"]}

@app.get("/findings")
def findings():
    findings = get_recent_findings()
    return {"total": len(findings), "recent": findings}
    return {
        "total": len(FINDINGS_STORE),
        "recent": FINDINGS_STORE[-10:]  # Last 10 findings
    }

@app.post("/findings")
def add_finding_api(finding: dict):
    add_finding(finding)
    return {"status": "added"}
    """Endpoint for agents to submit new findings"""
    finding["id"] = len(FINDINGS_STORE) + 1
    finding["created_at"] = datetime.now().isoformat()
    FINDINGS_STORE.append(finding)
    return {"status": "added", "id": finding["id"]}

@app.get("/debug-files")
def debug_files():
    """Debug endpoint to see file structure"""
    cwd = os.getcwd()
    files_in_cwd = os.listdir(cwd) if os.path.exists(cwd) else []

    # Check various paths
    ui_path = os.path.join(cwd, "ui")
    ui_exists = os.path.exists(ui_path)
    ui_files = os.listdir(ui_path) if ui_exists else []

    static_path = os.path.join(cwd, "ui", "static")
    static_exists = os.path.exists(static_path)
    static_files = os.listdir(static_path) if static_exists else []

    html_path = os.path.join(STATIC_DIR, "index.html")
    html_exists = os.path.exists(html_path)

    return {
        "current_working_directory": cwd,
        "files_in_cwd": files_in_cwd,
        "ui_directory_exists": ui_exists,
        "ui_files": ui_files,
        "static_directory_exists": static_exists,
        "static_files": static_files,
        "html_file_exists": html_exists,
        "looking_for_path": html_path,
        "base_dir": BASE_DIR,
        "static_dir": STATIC_DIR
    }

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/test")
def test():
    return {"message": "Server is working!", "routes": ["dashboard", "agents", "findings", "health", "debug-files", "test"]}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting server on port {port}")
    print(f"Environment PORT: {os.environ.get('PORT', 'Not set')}")
    uvicorn.run(app, host="0.0.0.0", port=port)

# --- OHLCV Route ---

from fastapi import APIRouter
import ccxt
from datetime import datetime

router = APIRouter()

@router.get("/ohlcv")
def get_ohlcv():
    try:
        exchange = ccxt.binance()
        since = exchange.milliseconds() - 30 * 24 * 60 * 60 * 1000  # 30 days ago
        ohlcv = exchange.fetch_ohlcv('BTC/USDT', timeframe='1d', since=since)

        data = []
        for entry in ohlcv:
            timestamp, open_, high, low, close, _ = entry
            date_str = datetime.utcfromtimestamp(timestamp / 1000).strftime('%Y-%m-%d')
            data.append({
                'x': date_str,
                'open': open_,
                'high': high,
                'low': low,
                'close': close
            })

        return {"data": data}

    except Exception as e:
        return {"error": str(e)}

app.include_router(router)


@app.get("/schedule")
def list_schedules():
    return {"active": get_schedules()}

@app.post("/schedule")
def schedule_toggle(data: dict):
    agent = data.get("agent")
    interval = int(data.get("interval", 60))
    action = data.get("action")
    if action == "add":
        schedule_agent(agent, interval)
        return {"status": f"{agent} scheduled every {interval} min"}
    elif action == "remove":
        remove_agent(agent)
        return {"status": f"{agent} unscheduled"}
    return {"error": "Invalid request"}


start_scheduler()
