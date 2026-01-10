import json
import math
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone

RECON = Path("alpha/reconciled.jsonl")
STATE = Path("meta_supervisor/state/confidence_multipliers.json")

HORIZON_HOURS = 24

HALF_LIFE_SIGNALS = 80

LOSS_K_BPS = 50.0

FLOOR = 0.50
CEIL = 1.10

PENALTY_CAP = 0.08

LOSS_AMPLIFIER = 1.3

STABILITY_BOOST = 0.02
STABILITY_GOOD_ERR_BPS = 30.0
STABILITY_MIN_GOOD = 10


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def _load_state() -> dict:
    if not STATE.exists():
        return {"version": 1, "generated_at": None, "multipliers": {}}
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {"version": 1, "generated_at": None, "multipliers": {}}


def _save_state(s: dict):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, indent=2))


def _sigmoid_penalty(abs_error_bps: float) -> float:
    x = max(0.0, float(abs_error_bps))
    return (x / (x + LOSS_K_BPS)) * PENALTY_CAP


def update_confidence_multipliers(limit_rows: int = 8000) -> dict:
    recon = _load_jsonl(RECON)
    recon = [r for r in recon if int(r.get("horizon_hours", 0)) == HORIZON_HOURS]
    if not recon:
        state = {
            "version": 1,
            "generated_at": _now(),
            "multipliers": {}
        }
        _save_state(state)
        return state

    recon = recon[-limit_rows:]

    by_agent: dict[str, list[dict]] = defaultdict(list)
    for r in recon:
        a = r.get("agent") or "unknown"
        by_agent[a].append(r)

    prev = _load_state()
    prev_mult = prev.get("multipliers", {}) or {}

    lam = math.log(2.0) / max(HALF_LIFE_SIGNALS, 1)

    multipliers: dict[str, float] = dict(prev_mult)

    for agent, rows in by_agent.items():
        m = float(prev_mult.get(agent, 1.0))

        good = 0
        bad = 0

        n = len(rows)
        tail = rows[-250:]

        for i, r in enumerate(tail):
            try:
                abs_err = float(r.get("abs_error_bps", 0.0) or 0.0)
                realized = float(r.get("realized_pnl_bps", 0.0) or 0.0)
            except Exception:
                continue

            global_idx = (n - len(tail) + i)
            age = (n - 1 - global_idx)
            w = math.exp(-lam * max(age, 0))

            pen = _sigmoid_penalty(abs_err) * w
            if realized < 0:
                pen *= LOSS_AMPLIFIER

            m *= (1.0 - pen)

            if realized > 0 and abs_err <= STABILITY_GOOD_ERR_BPS:
                good += 1
            if realized < 0 and abs_err >= (STABILITY_GOOD_ERR_BPS * 2):
                bad += 1

        if good >= STABILITY_MIN_GOOD and bad == 0:
            m *= (1.0 + STABILITY_BOOST)

        m = max(FLOOR, min(CEIL, m))
        multipliers[agent] = round(m, 4)

    out = {"version": 1, "generated_at": _now(), "multipliers": multipliers}
    _save_state(out)
    return out


def get_confidence_multiplier(agent_name: str) -> float:
    state = _load_state()
    mult = (state.get("multipliers") or {}).get(agent_name)
    try:
        return float(mult) if mult is not None else 1.0
    except Exception:
        return 1.0


if __name__ == "__main__":
    print(json.dumps(update_confidence_multipliers(), indent=2))
