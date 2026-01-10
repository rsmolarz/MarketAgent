import json
from pathlib import Path

ALLOC = Path("meta_supervisor/state/allocation.json")
PREV = Path("meta_supervisor/state/allocation_prev.json")


def _load(p: Path):
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def snapshot_prev():
    """Snapshot current allocation as previous for next run"""
    if ALLOC.exists():
        PREV.write_text(ALLOC.read_text())


def capital_deltas(total_capital_usd: float):
    """Compute capital-at-risk deltas between current and previous allocation"""
    cur = _load(ALLOC)
    prev = _load(PREV)

    agents = set(cur.keys()) | set(prev.keys())
    rows = []
    for a in sorted(agents):
        w0 = float(prev.get(a, 0.0))
        w1 = float(cur.get(a, 0.0))
        d = w1 - w0
        rows.append({
            "agent": a,
            "prev_w": round(w0, 4),
            "cur_w": round(w1, 4),
            "delta_w": round(d, 4),
            "delta_capital_usd": round(d * total_capital_usd, 2),
            "capital_usd": round(w1 * total_capital_usd, 2),
        })
    rows.sort(key=lambda x: abs(x["delta_capital_usd"]), reverse=True)
    return rows
