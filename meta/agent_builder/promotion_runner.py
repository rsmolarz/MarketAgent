"""
Promotion Runner: Reads telemetry summaries and proposes cadence/capital adjustments.
Runs periodically and opens PRs for human approval.
"""
import json
from pathlib import Path
from datetime import datetime, timezone
import yaml

from meta.agent_builder.promotion_policy import promotion_decision, get_promotion_report
from telemetry.rolling_stats import _mean, _std, _drawdown

MANIFEST_PATH = Path("agents/manifest.yaml")
TELEMETRY_EVENTS = Path("telemetry/events.jsonl")
SCHEDULE_PATH = Path("agent_schedule.json")
PROMOTION_REPORT_PATH = Path("meta/reports/promotion_report.json")


def load_agent_stats(agent_name: str, window: int = 500) -> dict:
    """Load rolling stats for an agent from telemetry events."""
    if not TELEMETRY_EVENTS.exists():
        return {"count": 0}
    
    lines = TELEMETRY_EVENTS.read_text().splitlines()[-5000:]
    rewards = []
    
    for ln in lines:
        try:
            e = json.loads(ln)
            if e.get("agent") == agent_name and e.get("reward") is not None:
                rewards.append(float(e["reward"]))
        except Exception:
            continue
    
    rewards = rewards[-window:]
    
    if not rewards:
        return {"count": 0}
    
    return {
        "count": len(rewards),
        "avg_reward": _mean(rewards),
        "cap_reward_mean": _mean(rewards),
        "sharpe": _mean(rewards) / _std(rewards) if _std(rewards) > 1e-9 else 0.0,
        "drawdown": _drawdown(rewards)
    }


def load_schedule() -> dict:
    """Load current agent schedule."""
    if not SCHEDULE_PATH.exists():
        return {}
    return json.loads(SCHEDULE_PATH.read_text())


def load_manifest() -> dict:
    """Load agent manifest."""
    if not MANIFEST_PATH.exists():
        return {"agents": []}
    return yaml.safe_load(MANIFEST_PATH.read_text())


def calculate_new_interval(current_interval: int, decision: bool, reason: str) -> int:
    """
    Calculate new scheduling interval based on promotion decision.
    - Promote: reduce interval by 20% (run more often)
    - Hold: keep current or increase by 10% if struggling
    """
    if decision:
        new_interval = max(5, int(current_interval * 0.8))
    else:
        if reason in ("drawdown_too_deep", "sharpe_below_threshold"):
            new_interval = min(120, int(current_interval * 1.2))
        else:
            new_interval = current_interval
    
    return new_interval


def run_promotion_check() -> dict:
    """
    Run promotion checks for all agents and generate recommendations.
    Returns a report with proposed changes.
    """
    manifest = load_manifest()
    schedule = load_schedule()
    
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "agents": [],
        "proposed_changes": []
    }
    
    for agent_entry in manifest.get("agents", []):
        agent_name = agent_entry.get("name")
        if not agent_name:
            continue
        
        stats = load_agent_stats(agent_name)
        decision, reason = promotion_decision(stats)
        full_report = get_promotion_report(stats)
        
        current_interval = schedule.get(agent_name, 60)
        new_interval = calculate_new_interval(current_interval, decision, reason)
        
        agent_report = {
            "agent": agent_name,
            "stats": stats,
            "decision": "promote" if decision else "hold",
            "reason": reason,
            "current_interval": current_interval,
            "proposed_interval": new_interval,
            "checks": full_report["checks"]
        }
        report["agents"].append(agent_report)
        
        if new_interval != current_interval:
            report["proposed_changes"].append({
                "agent": agent_name,
                "current_interval": current_interval,
                "proposed_interval": new_interval,
                "reason": reason
            })
    
    return report


def apply_proposed_changes(report: dict, dry_run: bool = True) -> dict:
    """
    Apply proposed interval changes to schedule.
    
    Args:
        report: The promotion report with proposed changes
        dry_run: If True, only return what would change without applying
    
    Returns:
        dict with applied changes
    """
    schedule = load_schedule()
    applied = []
    
    for change in report.get("proposed_changes", []):
        agent_name = change["agent"]
        new_interval = change["proposed_interval"]
        
        if not dry_run:
            schedule[agent_name] = new_interval
            applied.append(change)
        else:
            applied.append({**change, "dry_run": True})
    
    if not dry_run and applied:
        SCHEDULE_PATH.write_text(json.dumps(schedule, indent=2))
    
    return {"applied": applied, "dry_run": dry_run}


def main():
    """Run promotion check and save report."""
    report = run_promotion_check()
    
    Path("meta/reports").mkdir(parents=True, exist_ok=True)
    PROMOTION_REPORT_PATH.write_text(json.dumps(report, indent=2))
    
    print(f"Promotion report generated: {PROMOTION_REPORT_PATH}")
    print(f"Agents checked: {len(report['agents'])}")
    print(f"Proposed changes: {len(report['proposed_changes'])}")
    
    for change in report["proposed_changes"]:
        print(f"  - {change['agent']}: {change['current_interval']}m -> {change['proposed_interval']}m ({change['reason']})")
    
    return report


if __name__ == "__main__":
    main()
