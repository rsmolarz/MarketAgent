import json
from pathlib import Path
from collections import defaultdict

def summarize(path="telemetry/events.jsonl", last_n=2000):
    p = Path(path)
    if not p.exists():
        return {"available": False, "by_agent": {}}

    lines = p.read_text().splitlines()[-last_n:]
    by = defaultdict(lambda: {"count": 0, "errors": 0, "lat_ms": [], "cost": []})

    for line in lines:
        try:
            e = json.loads(line)
        except:
            continue
        a = e.get("agent", "unknown")
        by[a]["count"] += 1
        if e.get("error"):
            by[a]["errors"] += 1
        if e.get("latency_ms") is not None:
            by[a]["lat_ms"].append(e["latency_ms"])
        if e.get("cost_usd") is not None:
            by[a]["cost"].append(e["cost_usd"])

    out = {}
    for a, v in by.items():
        lat = sorted(v["lat_ms"])
        def pct(p):
            if not lat:
                return None
            i = int((p / 100) * (len(lat) - 1))
            return lat[i]
        out[a] = {
            "count": v["count"],
            "error_rate": (v["errors"] / v["count"]) if v["count"] else 0,
            "p50_latency_ms": pct(50),
            "p95_latency_ms": pct(95),
            "avg_cost_usd": (sum(v["cost"]) / len(v["cost"])) if v["cost"] else None
        }

    return {"available": True, "by_agent": out}
