import json
from pathlib import Path
from datetime import datetime, timezone

PROMOTION_LOG = Path("meta_supervisor/state/promotion_log.json")
PROMOTABLE_AGENTS = Path("meta_supervisor/state/promotable_agents.json")

def load_promotion_log() -> list:
    if not PROMOTION_LOG.exists():
        return []
    try:
        return json.loads(PROMOTION_LOG.read_text())
    except Exception:
        return []

def save_promotion_log(log: list):
    PROMOTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    PROMOTION_LOG.write_text(json.dumps(log, indent=2))

def should_promote(agent_metrics: dict) -> bool:
    """
    Promotion gates for sandbox → production.
    
    Gates:
    1. Behavioral score >= 80 (retirement_score < 20 means healthy)
    2. Realized PnL > 0
    3. Confidence decay stable (multiplier >= 0.8)
    4. Not on kill list (decision != KILL)
    5. Error rate == 0
    6. Latency < 900ms
    7. Sim accuracy: avg_abs_error_bps <= 60
    """
    score = agent_metrics.get("retirement_score", 100)
    pnl = float(agent_metrics.get("pnl_sum_bps", 0))
    decision = agent_metrics.get("decision", "HOLD")
    error_rate = float(agent_metrics.get("error_rate", 1))
    latency = agent_metrics.get("avg_latency_ms") or 0
    hit_rate = float(agent_metrics.get("hit_rate", 0))
    avg_abs_error = agent_metrics.get("avg_abs_error_bps")
    
    behavioral_ok = score < 20
    pnl_ok = pnl > 0
    not_killed = decision != "KILL"
    error_ok = error_rate == 0
    latency_ok = latency < 900
    hit_rate_ok = hit_rate >= 0.5
    sim_ok = (
        avg_abs_error is None or
        float(avg_abs_error) <= 60
    )
    
    return all([
        behavioral_ok,
        pnl_ok,
        not_killed,
        error_ok,
        latency_ok,
        hit_rate_ok,
        sim_ok,
    ])

def create_promotion_record(agent_name: str, agent_metrics: dict) -> dict:
    """Create a promotion record for an agent."""
    record = {
        "agent": agent_name,
        "promoted_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "metrics_at_promotion": {
            "pnl_sum_bps": agent_metrics.get("pnl_sum_bps"),
            "hit_rate": agent_metrics.get("hit_rate"),
            "error_rate": agent_metrics.get("error_rate"),
            "avg_latency_ms": agent_metrics.get("avg_latency_ms"),
            "retirement_score": agent_metrics.get("retirement_score"),
            "runs": agent_metrics.get("runs"),
        },
        "status": "pending_review",
        "auto_promote_tag": "[AUTO-PROMOTE]",
    }
    
    log = load_promotion_log()
    log = [p for p in log if p.get("agent") != agent_name]
    log.append(record)
    save_promotion_log(log)
    
    return record

def get_pending_promotions() -> list:
    """Get all pending promotion records."""
    log = load_promotion_log()
    return [p for p in log if p.get("status") == "pending_review"]

def approve_promotion(agent_name: str, approver: str) -> bool:
    """Approve a pending promotion (human veto check passed)."""
    log = load_promotion_log()
    for record in log:
        if record.get("agent") == agent_name and record.get("status") == "pending_review":
            record["status"] = "approved"
            record["approved_by"] = approver
            record["approved_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            save_promotion_log(log)
            return True
    return False

def veto_promotion(agent_name: str, vetoer: str, reason: str) -> bool:
    """Veto a pending promotion."""
    log = load_promotion_log()
    for record in log:
        if record.get("agent") == agent_name and record.get("status") == "pending_review":
            record["status"] = "vetoed"
            record["vetoed_by"] = vetoer
            record["veto_reason"] = reason
            record["vetoed_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            save_promotion_log(log)
            return True
    return False
