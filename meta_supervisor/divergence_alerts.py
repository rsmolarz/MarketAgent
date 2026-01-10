import json
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

RECON = Path("alpha/reconciled.jsonl")
ALERTS = Path("meta_supervisor/state/divergence_alerts.json")


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_jsonl(p: Path):
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def detect(window: int = 80, horizon_hours: int = 24, abs_err_thr: float = 90.0, mean_err_thr: float = 40.0):
    rows = [r for r in _load_jsonl(RECON) if int(r.get("horizon_hours", 0)) == horizon_hours]
    rows = rows[-8000:]

    by_agent = defaultdict(list)
    for r in rows:
        by_agent[r.get("agent", "unknown")].append(r)

    alerts = []
    for agent, rs in by_agent.items():
        tail = rs[-window:]
        abs_err = [float(x.get("abs_error_bps", 0) or 0) for x in tail if x.get("abs_error_bps") is not None]
        err = [float(x.get("pnl_error_bps", 0) or 0) for x in tail if x.get("pnl_error_bps") is not None]
        if len(abs_err) < max(10, window // 4):
            continue
        m_abs = sum(abs_err) / len(abs_err)
        m_err = sum(err) / len(err)
        if m_abs >= abs_err_thr or abs(m_err) >= mean_err_thr:
            alerts.append({
                "ts": _now(),
                "agent": agent,
                "window": len(abs_err),
                "mean_abs_error_bps": round(m_abs, 2),
                "mean_error_bps": round(m_err, 2),
                "severity": "high" if m_abs >= abs_err_thr * 1.3 else "medium",
                "action": "REDUCE_ALLOC_AND_BLOCK_PROMOTION"
            })

    result = {"generated_at": _now(), "alerts": alerts}
    ALERTS.parent.mkdir(parents=True, exist_ok=True)
    ALERTS.write_text(json.dumps(result, indent=2))
    return alerts


if __name__ == "__main__":
    print(json.dumps(detect(), indent=2))
