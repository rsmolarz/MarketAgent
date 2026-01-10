import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

def rollup(events_path="telemetry/events.jsonl", out_path="telemetry/summary.json"):
    events_file = Path(events_path)
    if not events_file.exists():
        return {}
    
    lines = events_file.read_text().splitlines()
    
    by_agent = defaultdict(lambda: {
        "count": 0,
        "total_latency_ms": 0,
        "total_cost_usd": 0.0,
        "total_reward": 0.0,
        "errors": 0,
    })
    
    for line in lines:
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except:
            continue
        
        agent = e.get("agent", "unknown")
        stats = by_agent[agent]
        
        stats["count"] += 1
        stats["total_latency_ms"] += e.get("latency_ms") or 0
        stats["total_cost_usd"] += e.get("cost_usd") or 0.0
        stats["total_reward"] += e.get("reward") or 0.0
        if e.get("error"):
            stats["errors"] += 1
    
    summary = {}
    for agent, stats in by_agent.items():
        n = stats["count"]
        summary[agent] = {
            "count": n,
            "avg_latency_ms": round(stats["total_latency_ms"] / max(n, 1), 2),
            "total_cost_usd": round(stats["total_cost_usd"], 4),
            "avg_reward": round(stats["total_reward"] / max(n, 1), 4),
            "error_rate": round(stats["errors"] / max(n, 1), 4),
        }
    
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "agents": summary
    }, indent=2))
    
    return summary

if __name__ == "__main__":
    s = rollup()
    print(json.dumps(s, indent=2))
