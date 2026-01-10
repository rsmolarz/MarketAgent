import json
from pathlib import Path
from datetime import datetime, timezone

RECON = Path("alpha/reconciled.jsonl")
TEL = Path("telemetry/events.jsonl")
OUT = Path("meta_supervisor/research/failure_forensics.json")

FOCUS_HORIZON = 24
TOP_N = 25

def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def _load_jsonl(p: Path):
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]

def run():
    recon = [r for r in _load_jsonl(RECON) if int(r.get("horizon_hours", 0)) == FOCUS_HORIZON]
    tel = _load_jsonl(TEL)
    tel_by_run = {t.get("run_id"): t for t in tel if t.get("run_id")}

    joined = []
    for r in recon:
        rid = r.get("run_id")
        joined.append({**r, **tel_by_run.get(rid, {})})

    worst = sorted(joined, key=lambda x: float(x.get("realized_pnl_bps", 0.0)))[:TOP_N]

    by_agent = {}
    for e in worst:
        by_agent.setdefault(e.get("agent", "unknown"), []).append(e)

    agent_summaries = []
    for agent, rows in by_agent.items():
        pnls = [float(x.get("realized_pnl_bps", 0.0)) for x in rows]
        lats = sorted([int(x.get("latency_ms", 0)) for x in rows if x.get("latency_ms") is not None])
        toks = sorted([(int(x.get("tokens_in", 0)) + int(x.get("tokens_out", 0))) for x in rows])
        errs = [int(x.get("errors", 0)) for x in rows]

        agent_summaries.append({
            "agent": agent,
            "loss_count": len(rows),
            "avg_loss_bps": round(sum(pnls) / max(len(pnls), 1), 2),
            "median_latency_ms": lats[len(lats) // 2] if lats else None,
            "median_tokens": toks[len(toks) // 2] if toks else None,
            "error_rate": round(sum(errs) / max(len(errs), 1), 3),
            "example_runs": rows[:5],
            "why_we_lost_hypotheses": [
                "Regime mismatch (edge not conditioned on regime).",
                "Liquidity/vol shock; gating insufficient.",
                "Confidence sizing too sticky; needs faster decay.",
                "Agent cost/latency spikes correlate with bad fills (proxy).",
            ],
        })

    out = {
        "generated_at": _now(),
        "horizon_hours": FOCUS_HORIZON,
        "worst_runs": worst,
        "by_agent": sorted(agent_summaries, key=lambda x: x["avg_loss_bps"]),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2))
    return out

if __name__ == "__main__":
    run()
