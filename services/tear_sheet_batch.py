import json
import math
from pathlib import Path
from datetime import datetime, timezone

RECON = Path("alpha/reconciled.jsonl")
REPORT = Path("meta_supervisor/reports/meta_report.json")
OUT_DIR = Path("reports/tear_sheets")

def load_jsonl(p: Path):
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]

def load_report():
    if not REPORT.exists():
        return {}
    return json.loads(REPORT.read_text())

def compute_sharpe(pnls: list[float]) -> float:
    """Compute Sharpe ratio approximation"""
    if len(pnls) < 2:
        return 0
    avg = sum(pnls) / len(pnls)
    variance = sum((p - avg) ** 2 for p in pnls) / len(pnls)
    std = math.sqrt(variance) if variance > 0 else 1
    return round((avg / std) * math.sqrt(252), 3) if std > 0 else 0

def compute_max_drawdown(pnls: list[float]) -> float:
    """Compute max drawdown in bps"""
    if not pnls:
        return 0
    cumulative = 0
    peak = 0
    max_dd = 0
    for p in pnls:
        cumulative += p
        peak = max(peak, cumulative)
        max_dd = min(max_dd, cumulative - peak)
    return round(abs(max_dd), 2)

def build_tear_sheet(agent: str, pnls: list[float], stats: dict) -> dict:
    """Build investor-grade tear sheet for an agent"""
    if not pnls:
        return {}
    
    total_pnl = sum(pnls)
    hit_rate = sum(1 for p in pnls if p > 0) / max(len(pnls), 1)
    sharpe = compute_sharpe(pnls)
    max_dd = compute_max_drawdown(pnls)
    
    avg_win = sum(p for p in pnls if p > 0) / max(sum(1 for p in pnls if p > 0), 1)
    avg_loss = sum(p for p in pnls if p < 0) / max(sum(1 for p in pnls if p < 0), 1)
    profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
    
    return {
        "agent": agent,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "summary": {
            "total_pnl_bps": round(total_pnl, 2),
            "trades": len(pnls),
            "hit_rate": round(hit_rate, 3),
            "sharpe_ratio": sharpe,
            "max_drawdown_bps": max_dd,
            "profit_factor": round(profit_factor, 2) if profit_factor != float('inf') else "inf",
        },
        "performance": {
            "avg_win_bps": round(avg_win, 2),
            "avg_loss_bps": round(avg_loss, 2),
            "best_trade_bps": round(max(pnls), 2) if pnls else 0,
            "worst_trade_bps": round(min(pnls), 2) if pnls else 0,
        },
        "risk": {
            "volatility_bps": round(math.sqrt(sum((p - total_pnl/len(pnls))**2 for p in pnls)/len(pnls)), 2) if len(pnls) > 1 else 0,
            "downside_deviation": round(math.sqrt(sum(min(0, p)**2 for p in pnls)/len(pnls)), 2) if pnls else 0,
        },
        "agent_stats": {
            "decision": stats.get("decision", "HOLD"),
            "retirement_score": stats.get("retirement_score", 0),
            "error_rate": stats.get("error_rate", 0),
            "avg_latency_ms": stats.get("avg_latency_ms"),
        },
    }

def build_all(top_n: int = 10, horizon_hours: int = 24) -> list[dict]:
    """Build tear sheets for top N agents by PnL"""
    recon = [r for r in load_jsonl(RECON) if int(r.get("horizon_hours", 0)) == horizon_hours]
    report = load_report()
    agents_stats = report.get("agents", {})
    
    by_agent = {}
    for r in recon:
        agent = r.get("agent", "unknown")
        pnl = float(r.get("realized_pnl_bps", 0))
        by_agent.setdefault(agent, []).append(pnl)
    
    agent_totals = [(agent, sum(pnls)) for agent, pnls in by_agent.items()]
    top_agents = sorted(agent_totals, key=lambda x: x[1], reverse=True)[:top_n]
    
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    
    tear_sheets = []
    for agent, _ in top_agents:
        pnls = by_agent.get(agent, [])
        stats = agents_stats.get(agent, {})
        sheet = build_tear_sheet(agent, pnls, stats)
        
        if sheet:
            out_path = OUT_DIR / f"{agent}.json"
            out_path.write_text(json.dumps(sheet, indent=2))
            tear_sheets.append(sheet)
    
    summary_path = OUT_DIR / "_summary.json"
    summary_path.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "agents": [s["agent"] for s in tear_sheets],
        "count": len(tear_sheets),
    }, indent=2))
    
    return tear_sheets

if __name__ == "__main__":
    sheets = build_all()
    print(f"Built {len(sheets)} tear sheets")
    for s in sheets:
        print(f"  {s['agent']}: {s['summary']['total_pnl_bps']} bps")
