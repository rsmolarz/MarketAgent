import json
from pathlib import Path
from datetime import datetime, timezone

RECON = Path("alpha/reconciled.jsonl")
TEL = Path("telemetry/events.jsonl")
OUT = Path("meta_supervisor/research/failure_forensics.json")

FOCUS_HORIZON = 24
TOP_N = 50

def load_jsonl(p: Path):
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]

def run():
    recon = [r for r in load_jsonl(RECON) if int(r.get("horizon_hours", 0)) == FOCUS_HORIZON]
    tel = load_jsonl(TEL)

    tel_by_run = {t.get("run_id"): t for t in tel if t.get("run_id")}
    joined = []
    for r in recon:
        rid = r.get("run_id")
        joined.append({**r, **(tel_by_run.get(rid, {}))})

    worst = sorted(joined, key=lambda e: float(e.get("realized_pnl_bps", 0.0)))[:TOP_N]

    by_agent = {}
    for e in worst:
        a = e.get("agent", "unknown")
        by_agent.setdefault(a, []).append(e)

    summaries = []
    for agent, rows in by_agent.items():
        pnls = [float(x.get("realized_pnl_bps", 0.0)) for x in rows]
        lats = [int(x.get("latency_ms", 0)) for x in rows if x.get("latency_ms") is not None]
        toks = [int(x.get("tokens_in", 0)) + int(x.get("tokens_out", 0)) for x in rows]
        errs = [int(x.get("errors", 0)) for x in rows]

        summaries.append({
            "agent": agent,
            "loss_count": len(rows),
            "avg_loss_bps": round(sum(pnls)/max(len(pnls),1), 2),
            "median_latency_ms": sorted(lats)[len(lats)//2] if lats else None,
            "median_tokens": sorted(toks)[len(toks)//2] if toks else None,
            "error_rate": round(sum(errs)/max(len(errs),1), 3),
            "example_runs": rows[:5],
            "hypotheses": [
                "Regime mismatch (edge not conditioned on regime).",
                "Liquidity/volatility shock (needs gating).",
                "Confidence not decaying after losses (position sizing too sticky).",
            ],
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
        "horizon_hours": FOCUS_HORIZON,
        "worst_runs": worst[:10],
        "by_agent": sorted(summaries, key=lambda x: x["avg_loss_bps"])
    }, indent=2))

    return summaries

if __name__ == "__main__":
    run()
