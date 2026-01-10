import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone

RECON = Path("alpha/reconciled.jsonl")
OUT = Path("meta_supervisor/state/strategy_cvar_regime.json")


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_jsonl(p: Path):
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def cvar(values, alpha=0.95):
    if not values:
        return 0.0
    vs = sorted(values)
    cutoff = int(len(vs) * alpha)
    tail = vs[cutoff:]
    return sum(tail) / max(len(tail), 1)


def run(horizon_hours: int = 24):
    rows = [r for r in _load_jsonl(RECON) if int(r.get("horizon_hours", 0)) == horizon_hours]
    rows = rows[-8000:]

    by_key = defaultdict(list)
    for r in rows:
        strat = r.get("strategy_class") or "unknown"
        regime = r.get("regime") or "unknown"
        pe = r.get("pnl_error_bps")
        if pe is None:
            continue
        by_key[(strat, regime)].append(float(pe))

    out = {}
    for (s, g), vals in by_key.items():
        out.setdefault(s, {})[g] = {
            "n": len(vals),
            "cvar95_error_bps": round(cvar(vals, 0.95), 2),
            "mean_error_bps": round(sum(vals) / max(len(vals), 1), 2),
        }

    result = {
        "generated_at": _now(),
        "horizon_hours": horizon_hours,
        "by_strategy_regime": out,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
