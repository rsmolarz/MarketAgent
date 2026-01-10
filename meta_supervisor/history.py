import json
from pathlib import Path
from datetime import datetime, timezone

HIST = Path("meta_supervisor/state/allocation_history.jsonl")

def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def append_allocation_snapshot(report: dict, run_id: str | None = None):
    HIST.parent.mkdir(parents=True, exist_ok=True)
    alloc = report.get("allocation", {}) or {}
    fleet = report.get("fleet", {}) or {}
    meta = report.get("meta", {}) or {}

    event = {
        "ts": meta.get("generated_at") or _now(),
        "run_id": run_id,
        "method": alloc.get("method"),
        "weights": alloc.get("weights", {}) or {},
        "portfolio_pnl_bps": fleet.get("portfolio_pnl_bps"),
        "portfolio_max_dd_bps": fleet.get("portfolio_max_drawdown_bps"),
    }
    with open(HIST, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")
    return event

def load_history(limit: int = 10000) -> list[dict]:
    if not HIST.exists():
        return []
    rows = [json.loads(x) for x in HIST.read_text().splitlines() if x.strip()]
    return rows[-limit:]
