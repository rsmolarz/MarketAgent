import json
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from meta_supervisor.retirement import retirement_score, retirement_label
from meta_supervisor.portfolio import portfolio_from_alpha
from meta_supervisor.proposal_scoring import score_proposal
from meta_supervisor.allocation import main as alloc_main
from meta_supervisor.confidence_decay import update_confidence_multipliers

from meta_supervisor.risk_metrics import var_cvar, max_drawdown_bps
from meta_supervisor.allocation_cvar import compute_cvar_weights
from meta_supervisor.regime import compute_regime_multipliers, get_regime_multiplier
from meta_supervisor.state.fleet_state import save_fleet
from meta_supervisor.capital import capital_at_risk_by_agent
from meta_supervisor.auto_kill import apply_auto_kills
from meta_supervisor.strategy_cvar import run as strategy_cvar_run
from meta_supervisor.lineage import get_lineage

PROPOSALS_PATH = Path("meta_supervisor/agent_proposals.json")
TEL = Path("telemetry/events.jsonl")
RECON = Path("alpha/reconciled.jsonl")
ALPHA = Path("alpha/events.jsonl")

def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def load_jsonl(path):
    if not Path(path).exists():
        return []
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]

def _load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text())
    except Exception:
        return default

def main():
    telemetry = load_jsonl(TEL)
    alpha = load_jsonl(ALPHA)
    recon = load_jsonl(RECON)

    recon24 = [r for r in recon if int(r.get("horizon_hours", 0)) == 24]

    try:
        regime_multipliers = compute_regime_multipliers(horizon_hours=24)
    except Exception:
        regime_multipliers = {}

    tel_by_run = {t.get("run_id"): t for t in telemetry if t.get("run_id")}
    joined = [{**r, **tel_by_run.get(r.get("run_id"), {})} for r in recon24]

    by_agent = {}

    for t in telemetry:
        a = t.get("agent", "unknown")
        by_agent.setdefault(a, {}).setdefault("telemetry", []).append(t)

    for e in alpha:
        a = e.get("agent", "unknown")
        by_agent.setdefault(a, {}).setdefault("alpha", []).append(e)

    for j in joined:
        a = j.get("agent", "unknown")
        by_agent.setdefault(a, {}).setdefault("reconciled", []).append(j)

    report = {"agents": {}}

    for agent, data in by_agent.items():
        tel = data.get("telemetry", [])
        alp = data.get("alpha", [])
        rec = data.get("reconciled", [])

        pnl_sum = sum(float(r.get("realized_pnl_bps", 0)) for r in rec)
        hit_count = sum(1 for r in rec if float(r.get("realized_pnl_bps", 0)) > 0)
        error_count = sum(1 for t in tel if t.get("errors", 0) > 0)
        latencies = [t.get("latency_ms", 0) for t in tel if t.get("latency_ms")]
        cost_sum = sum(float(t.get("cost_usd", 0)) for t in tel)

        pnl_series = [float(r.get("realized_pnl_bps", 0)) for r in rec]

        v, c = var_cvar(pnl_series, alpha=0.95)
        dd = max_drawdown_bps(pnl_series)

        last_regime = None
        if rec:
            last_regime = rec[-1].get("regime") or rec[-1].get("regime_label")
        reg_mult = get_regime_multiplier(last_regime) if last_regime else 1.0

        agent_stats = {
            "runs": len(tel),
            "avg_latency_ms": round(sum(latencies) / max(len(latencies), 1), 1) if latencies else None,
            "tokens": sum(t.get("tokens_in", 0) + t.get("tokens_out", 0) for t in tel),
            "alpha_signals": len(alp),
            "reconciled_signals": len(rec),
            "pnl_sum_bps": round(pnl_sum, 2),
            "hit_rate": round(hit_count / max(len(rec), 1), 3) if rec else 0,
            "error_rate": round(error_count / max(len(tel), 1), 3) if tel else 0,
            "cost_usd": round(cost_sum, 6),
            "var_95_bps": v,
            "cvar_95_bps": c,
            "max_dd_bps": dd,
            "last_regime": last_regime,
            "regime_multiplier": reg_mult,
        }

        score = retirement_score(agent_stats)
        agent_stats["retirement_score"] = score
        agent_stats["retirement_action"] = retirement_label(score)

        if (
            agent_stats["pnl_sum_bps"] < -150
            or agent_stats["error_rate"] > 0.2
            or agent_stats["max_dd_bps"] > 350
            or agent_stats["cvar_95_bps"] < -120
        ):
            agent_stats["decision"] = "KILL"
        elif (
            agent_stats["pnl_sum_bps"] > 150
            and agent_stats["hit_rate"] >= 0.55
            and agent_stats["error_rate"] == 0
            and (agent_stats["avg_latency_ms"] or 0) < 900
        ):
            agent_stats["decision"] = "PROMOTE"
        elif score >= 80:
            agent_stats["decision"] = "KILL"
        else:
            agent_stats["decision"] = "HOLD"

        report["agents"][agent] = agent_stats

    fleet = portfolio_from_alpha(recon24 if recon24 else alpha)
    report["fleet"] = fleet
    save_fleet(fleet)
    report["meta"] = {
        "generated_at": _now(),
        "severity": "high" if fleet.get("portfolio_pnl_bps", 0) < 0 else "low",
        "regime_multipliers": regime_multipliers,
    }

    confidence_state = update_confidence_multipliers()

    agent_pnls = {}
    for r in recon24:
        a = r.get("agent", "unknown")
        agent_pnls.setdefault(a, []).append(float(r.get("realized_pnl_bps", 0.0)))

    try:
        weights = compute_cvar_weights(agent_pnls, report["agents"], alpha=0.95)
        allocation_method = "cvar_95"
    except Exception:
        weights = alloc_main(report["agents"])
        allocation_method = "legacy"

    if weights:
        adjusted = {}
        for agent, w in weights.items():
            w_val = float(w) if w is not None else 0.0
            rm_raw = report["agents"].get(agent, {}).get("regime_multiplier", 1.0)
            rm = float(rm_raw) if rm_raw is not None else 1.0
            adjusted[agent] = w_val * rm
        s = sum(adjusted.values())
        if s > 0:
            weights = {k: round(v / s, 4) for k, v in adjusted.items()}

    report["allocation"] = {
        "method": allocation_method,
        "weights": weights,
        "confidence_state": confidence_state,
    }

    if PROPOSALS_PATH.exists():
        data = json.loads(PROPOSALS_PATH.read_text())
        for p in data.get("proposals", []):
            p["score"] = score_proposal(p)
        report["agent_proposals"] = sorted(
            data.get("proposals", []),
            key=lambda x: x.get("score", 0),
            reverse=True
        )

    report["research"] = {
        "literature_scan": _load_json("meta_supervisor/research/literature_scan.json", {}),
        "failure_forensics": _load_json("meta_supervisor/research/failure_forensics.json", {}),
    }
    report["regime_proposals"] = _load_json("meta_supervisor/agent_proposals_regime.json", {})

    report["capital"] = capital_at_risk_by_agent(report["allocation"]["weights"], report)
    report["strategy_cvar"] = strategy_cvar_run(horizon_hours=24)
    report["auto_kill"] = apply_auto_kills(report)
    report["lineage"] = get_lineage()

    Path("meta_supervisor/reports").mkdir(parents=True, exist_ok=True)
    Path("meta_supervisor/reports/meta_report.json").write_text(
        json.dumps(report, indent=2)
    )
    return report

if __name__ == "__main__":
    main()
    print("Meta report generated: meta_supervisor/reports/meta_report.json")
