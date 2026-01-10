import json
from pathlib import Path

HIST = Path("meta_supervisor/state/allocation_history.jsonl")

def _load_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]

def capital_movement_table(n_snapshots: int = 14, top_n: int = 12) -> dict:
    rows = _load_jsonl(HIST)
    if len(rows) < 2:
        return {"ok": False, "reason": "insufficient_history"}

    window = rows[-n_snapshots:]
    w0 = window[0].get("weights", {}) or {}
    w1 = window[-1].get("weights", {}) or {}

    agents = list(set(w0.keys()) | set(w1.keys()))
    deltas = [(a, float(w0.get(a, 0)), float(w1.get(a, 0)), float(w1.get(a, 0)) - float(w0.get(a, 0))) for a in agents]
    deltas.sort(key=lambda t: abs(t[3]), reverse=True)

    return {
        "ok": True,
        "from_ts": window[0].get("ts"),
        "to_ts": window[-1].get("ts"),
        "top_moves": [{"agent": a, "w_from": round(x, 4), "w_to": round(y, 4), "delta": round(d, 4)} for a, x, y, d in deltas[:top_n]],
    }
