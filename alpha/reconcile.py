import json
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from alpha.prices_crypto import get_price
from alpha.sim_model import predict as predict_expected
from meta_supervisor.agent_registry import AGENT_STRATEGY_CLASS

ALPHA = Path("alpha/events.jsonl")
OUT = Path("alpha/reconciled.jsonl")
PROCESSED_IDS = Path("alpha/.processed_run_ids.json")

HORIZONS_HOURS = [1, 4, 24]

SIM_VERSION = "v0.1-score-linear"
SCORE_TO_BPS = 25.0
MAX_EXPECTED_BPS = 250.0

def load_jsonl(p: Path):
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]

def parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def expected_pnl_from_score(score_final: float | None) -> float:
    if score_final is None:
        return 0.0
    try:
        exp = float(score_final) * SCORE_TO_BPS
        return clamp(exp, -MAX_EXPECTED_BPS, MAX_EXPECTED_BPS)
    except Exception:
        return 0.0

def load_processed_ids() -> set:
    if not PROCESSED_IDS.exists():
        return set()
    try:
        return set(json.loads(PROCESSED_IDS.read_text()))
    except Exception:
        return set()

def save_processed_ids(ids: set):
    PROCESSED_IDS.parent.mkdir(parents=True, exist_ok=True)
    PROCESSED_IDS.write_text(json.dumps(list(ids)))

def main(limit: int | None = None):
    events = load_jsonl(ALPHA)
    if limit:
        events = events[-limit:]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    
    processed_ids = load_processed_ids()
    now = datetime.now(timezone.utc)

    reconciled = []
    new_processed = set()
    
    for e in events:
        run_id = e.get("run_id", "")
        symbol = e.get("symbol")
        direction = (e.get("direction") or "").upper()
        ts = e.get("ts")
        if not symbol or direction not in ("LONG", "SHORT") or not ts:
            continue

        t0 = parse_ts(ts)

        for h in HORIZONS_HOURS:
            cache_key = f"{run_id}_{h}"
            if cache_key in processed_ids:
                continue
                
            t1 = t0 + timedelta(hours=h)
            
            if t1 > now:
                continue

            entry_px = get_price(symbol, t0.isoformat().replace("+00:00", "Z"), horizon_hours=h)
            exit_px = get_price(symbol, t1.isoformat().replace("+00:00", "Z"), horizon_hours=h)

            if not entry_px or not exit_px:
                continue

            if direction == "LONG":
                realized_pnl = (exit_px / entry_px - 1.0) * 10_000
            else:
                realized_pnl = (entry_px / exit_px - 1.0) * 10_000

            expected_pnl, expected_sigma, sim_version = predict_expected(
                score_final=e.get("score_final"),
                confidence=e.get("confidence"),
                horizon_hours=h
            )

            if expected_pnl is None:
                expected_pnl = expected_pnl_from_score(e.get("score_final"))
                expected_sigma = None
                sim_version = SIM_VERSION

            pnl_error = realized_pnl - expected_pnl
            abs_error = abs(pnl_error)

            agent_name = e.get("agent", "unknown")
            strategy_class = AGENT_STRATEGY_CLASS.get(agent_name, "unknown")

            reconciled.append({
                "ts": ts,
                "agent": agent_name,
                "run_id": run_id,
                "symbol": symbol,
                "direction": direction,
                "entry_price": entry_px,
                "exit_price": exit_px,
                "horizon_hours": h,
                "realized_pnl_bps": round(realized_pnl, 2),
                "expected_pnl_bps": round(expected_pnl, 2),
                "expected_sigma_bps": round(expected_sigma, 2) if expected_sigma is not None else None,
                "pnl_error_bps": round(pnl_error, 2),
                "abs_error_bps": round(abs_error, 2),
                "sim_version": sim_version,
                "strategy_class": strategy_class,
                "regime": e.get("regime"),
                "confidence": e.get("confidence"),
                "score_final": e.get("score_final"),
            })
            
            if run_id:
                new_processed.add(cache_key)

    if reconciled:
        with open(OUT, "a", encoding="utf-8") as f:
            for r in reconciled:
                f.write(json.dumps(r) + "\n")
        
        processed_ids.update(new_processed)
        save_processed_ids(processed_ids)

    return len(reconciled)

if __name__ == "__main__":
    n = main()
    print(f"Reconciled rows appended: {n}")
