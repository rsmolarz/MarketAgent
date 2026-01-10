import json
import sys
import logging
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from meta_supervisor.build_meta_report import main as build_report
from meta_supervisor.pr_comments import generate_pr_comment
from meta_supervisor.promotion import should_promote, create_promotion_record
from meta_supervisor.retirement import evaluate_retirements
from meta_supervisor.github_pr import maybe_create_pr
from meta_supervisor.strategy_attribution import run as run_strategy_attribution
from meta_supervisor.regime import compute_regime_multipliers
from meta_supervisor.divergence import compute_divergence
from meta_supervisor.history import append_allocation_snapshot
from meta_supervisor.scaffold import generate_agent_scaffold
from meta_supervisor.github_scaffold_pr import create_scaffold_pr
from meta_supervisor.risk.breach import drawdown_breach
from meta_supervisor.policy.kill_switch import disable_agents
from meta_supervisor.divergence_alerts import detect as detect_divergence
from meta_supervisor.strategy_cvar_regime import run as run_cvar_regime
from services.divergence_email import send_divergence_email
from services.tear_sheet_batch import build_all as build_tearsheets

logger = logging.getLogger(__name__)

SUPERVISOR_STATE = Path("meta_supervisor/state/supervisor_state.json")

def load_state():
    if not SUPERVISOR_STATE.exists():
        return {"last_run": None, "run_count": 0}
    try:
        return json.loads(SUPERVISOR_STATE.read_text())
    except Exception:
        return {"last_run": None, "run_count": 0}

def save_state(state: dict):
    SUPERVISOR_STATE.parent.mkdir(parents=True, exist_ok=True)
    SUPERVISOR_STATE.write_text(json.dumps(state, indent=2))

def run_meta_supervisor():
    """
    Main orchestrator for Meta-Supervisor evaluations.
    Runs on schedule (every 6 hours) or on-demand.
    """
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    logger.info(f"Meta-Supervisor starting run: {run_id}")

    state = load_state()
    state["run_count"] = state.get("run_count", 0) + 1
    state["last_run"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    state["current_run_id"] = run_id

    try:
        report = build_report()
        logger.info("Meta report generated")

        try:
            append_allocation_snapshot(report, run_id=run_id)
            logger.info("Allocation snapshot saved")
        except Exception as e:
            logger.warning(f"Allocation snapshot failed: {e}")

        try:
            regime_mult = compute_regime_multipliers(horizon_hours=24)
            report.setdefault("regime", {})["multipliers"] = regime_mult
            logger.info(f"Regime multipliers updated: {len(regime_mult)} regimes")
        except Exception as e:
            logger.warning(f"Regime multiplier update failed: {e}")
            regime_mult = {}

        div = {}
        try:
            div = compute_divergence(horizon_hours=24)
            if div.get("alert"):
                send_divergence_email()
            logger.info(f"Divergence: {div.get('divergence_bps')} bps | alert={div.get('alert')}")
        except Exception as e:
            logger.warning(f"Divergence check failed: {e}")
            div = {"error": str(e)}

        tearsheets = []
        try:
            tearsheets = build_tearsheets(top_n=10)
            logger.info(f"Tear sheets built: {len(tearsheets)}")
        except Exception as e:
            logger.warning(f"Tear sheet build failed: {e}")
            tearsheets = []

        retirements = evaluate_retirements(report)
        logger.info(f"Retirement evaluation: {len(retirements.get('to_kill', []))} agents flagged")

        if drawdown_breach(report.get("fleet", {})):
            promoted = [a for a, s in report.get("agents", {}).items() if s.get("decision") == "PROMOTE"]
            if promoted:
                disable_agents(promoted, reason="Auto-rollback: drawdown breach")
                logger.warning(f"Drawdown breach: disabled {len(promoted)} promoted agents")

        try:
            divergence_alerts = detect_divergence()
            if divergence_alerts:
                logger.warning(f"Divergence alerts detected: {len(divergence_alerts)} agents")
                report["divergence_alerts"] = divergence_alerts
        except Exception as e:
            logger.warning(f"Divergence detection failed: {e}")

        try:
            cvar_regime = run_cvar_regime()
            report["strategy_cvar_regime"] = cvar_regime
        except Exception as e:
            logger.warning(f"CVaR regime computation failed: {e}")

        promotions = []
        for agent_name, agent_data in report.get("agents", {}).items():
            if should_promote(agent_data):
                record = create_promotion_record(agent_name, agent_data)
                promotions.append(record)
                logger.info(f"Agent {agent_name} eligible for promotion")

        pr_comment = generate_pr_comment(
            run_id=run_id,
            report=report,
            retirements=retirements,
            promotions=promotions
        )

        result = {
            "run_id": run_id,
            "timestamp": state["last_run"],
            "report_summary": {
                "agents_evaluated": len(report.get("agents", {})),
                "portfolio_pnl_bps": report.get("fleet", {}).get("portfolio_pnl_bps", 0),
                "severity": report.get("meta", {}).get("severity", "unknown"),
            },
            "retirements": retirements,
            "promotions": promotions,
            "pr_comment": pr_comment,
            "divergence": div,
            "tear_sheets": [s["agent"] for s in tearsheets] if tearsheets else [],
            "regime_multipliers": regime_mult,
        }

        Path("meta_supervisor/reports").mkdir(parents=True, exist_ok=True)
        Path(f"meta_supervisor/reports/supervisor_run_{run_id}.json").write_text(
            json.dumps(result, indent=2)
        )

        try:
            strategy_result = run_strategy_attribution()
            logger.info(
                f"Strategy attribution: {strategy_result.get('strategies_evaluated', 0)} strategies, "
                f"{strategy_result.get('strategies_breached', 0)} breached"
            )
        except Exception as e:
            logger.warning(f"Strategy attribution error: {e}")

        try:
            pr_result = maybe_create_pr(report)
            if pr_result:
                logger.info(f"GitHub PR created: {pr_result}")
                result["github_pr"] = pr_result
        except Exception as e:
            logger.warning(f"GitHub PR creation error: {e}")

        scaffold_prs = []
        try:
            proposals = report.get("agent_proposals", [])
            for p in proposals:
                if p.get("status") == "APPROVED" and not p.get("pr_created"):
                    scaffold_result = generate_agent_scaffold(p)
                    pr = create_scaffold_pr(
                        agent_name=scaffold_result["agent_name"],
                        title=f"Scaffold agent: {p['name']}",
                        body=f"""
Agent proposal approved.

Strategy class: {p.get("strategy_class")}
Regime trigger: {p.get("regime_trigger")}

Auto-generated scaffold.
"""
                    )
                    p["pr_created"] = True
                    p["pr_url"] = pr.get("html_url")
                    scaffold_prs.append({"agent": p["name"], "pr_url": pr.get("html_url")})
                    logger.info(f"Scaffold PR created for {p['name']}: {pr.get('html_url')}")
            result["scaffold_prs"] = scaffold_prs
        except Exception as e:
            logger.warning(f"Scaffold PR creation error: {e}")

        state["last_result"] = "success"
        state["agents_evaluated"] = len(report.get("agents", {}))
        save_state(state)

        logger.info(f"Meta-Supervisor run {run_id} completed successfully")
        return result

    except Exception as e:
        logger.error(f"Meta-Supervisor error: {e}")
        state["last_result"] = f"error: {str(e)}"
        save_state(state)
        raise

if __name__ == "__main__":
    result = run_meta_supervisor()
    print(json.dumps(result, indent=2))
