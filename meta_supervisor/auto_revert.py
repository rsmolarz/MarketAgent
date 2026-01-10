import json
from pathlib import Path
from datetime import datetime, timezone
import yaml

RECON = Path("alpha/reconciled.jsonl")
KILL_LIST = Path("meta_supervisor/strategy_kill_list.yaml")


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_jsonl(p: Path):
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def _load_yaml(p: Path):
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text()) or {}


def cvar(values, alpha=0.95):
    if not values:
        return 0.0
    vs = sorted(values)
    cutoff = int(len(vs) * alpha)
    tail = vs[cutoff:]
    return sum(tail) / max(len(tail), 1)


def compute_strategy_metrics(strategy: str, horizon_hours: int = 24, window: int = 120):
    rows = [r for r in _load_jsonl(RECON) if int(r.get("horizon_hours", 0)) == horizon_hours]
    rows = [r for r in rows if (r.get("strategy_class") or "unknown") == strategy]
    tail = rows[-window:]

    pe = [float(r.get("pnl_error_bps", 0) or 0) for r in tail if r.get("pnl_error_bps") is not None]
    ae = [float(r.get("abs_error_bps", 0) or 0) for r in tail if r.get("abs_error_bps") is not None]

    return {
        "n": len(ae),
        "mean_abs_error_bps": round(sum(ae) / max(len(ae), 1), 2) if ae else None,
        "cvar95_error_bps": round(cvar(pe, 0.95), 2) if pe else None
    }


def find_reverts(
    horizon_hours: int = 24,
    window: int = 120,
    min_n: int = 40,
    max_mean_abs_error: float = 70.0,
    max_cvar95_error: float = 120.0
):
    kill = _load_yaml(KILL_LIST)
    to_revert = []

    for strat, cfg in kill.items():
        if (cfg or {}).get("status") != "DISABLED":
            continue

        m = compute_strategy_metrics(strat, horizon_hours=horizon_hours, window=window)
        if (m["n"] or 0) < min_n:
            continue
        if m["mean_abs_error_bps"] is None or m["cvar95_error_bps"] is None:
            continue

        if m["mean_abs_error_bps"] <= max_mean_abs_error and m["cvar95_error_bps"] <= max_cvar95_error:
            to_revert.append({
                "strategy": strat,
                "metrics": m,
                "reason": f"Recovered: mean_abs_error={m['mean_abs_error_bps']} <= {max_mean_abs_error}, cvar95_error={m['cvar95_error_bps']} <= {max_cvar95_error}"
            })
    return to_revert


def apply_reverts_to_yaml(reverts: list) -> str:
    kill = _load_yaml(KILL_LIST)
    for r in reverts:
        s = r["strategy"]
        kill.setdefault(s, {})
        kill[s]["status"] = "ACTIVE"
        kill[s]["re_enabled_at"] = _now()
        kill[s]["re_enable_reason"] = r["reason"]
    return yaml.dump(kill, default_flow_style=False)
