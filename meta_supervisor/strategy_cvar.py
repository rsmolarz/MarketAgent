import json
from pathlib import Path
from collections import defaultdict

RECONCILED = Path("alpha/reconciled.jsonl")

def load_reconciled():
    if not RECONCILED.exists():
        return []
    rows = []
    for line in RECONCILED.read_text().splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows

def run(horizon_hours: int = 24) -> dict:
    rows = load_reconciled()
    
    by_strategy = defaultdict(list)
    for r in rows:
        if r.get("horizon_hours") != horizon_hours:
            continue
        agent = r.get("agent", "unknown")
        strategy = agent.replace("Agent", "").lower() if agent else "unknown"
        
        realized = r.get("realized_pnl_bps", 0)
        expected = r.get("expected_pnl_bps", 0)
        gap = realized - expected
        by_strategy[strategy].append(gap)
    
    result = {}
    for strat, gaps in by_strategy.items():
        if len(gaps) < 3:
            result[strat] = {"gap_cvar95_bps": 0, "n": len(gaps)}
            continue
        
        sorted_gaps = sorted(gaps)
        cutoff = int(len(sorted_gaps) * 0.05)
        tail = sorted_gaps[:max(1, cutoff)]
        cvar = sum(tail) / len(tail)
        
        result[strat] = {
            "gap_cvar95_bps": round(cvar, 2),
            "n": len(gaps),
            "worst_gap": round(sorted_gaps[0], 2),
            "mean_gap": round(sum(gaps) / len(gaps), 2),
        }
    
    return result

if __name__ == "__main__":
    import json as j
    print(j.dumps(run(), indent=2))
