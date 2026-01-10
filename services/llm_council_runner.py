"""
LLM Council Runner - Single Entry Point

Consolidates all LLM council logic:
- Per-finding consensus persistence
- Disagreement detection and uncertainty spikes
- Fail-first learning per agent per regime
- Confidence boosting when TA aligns
"""
from datetime import datetime
import logging
from typing import Optional, Dict, Any

from models import (
    db,
    Finding,
    LLMCouncilResult,
    UncertaintyEvent,
    AgentCouncilStat,
)

logger = logging.getLogger(__name__)

DISAGREEMENT_SPIKE = 0.55
ACT_THRESHOLD = 0.60


def run_llm_council_for_finding(
    finding_id: int, 
    active_regime: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Run LLM council on a finding and persist all canonical fields.
    
    This is the single entry point for all council operations.
    Returns the council result dict or None if skipped/failed.
    """
    try:
        finding = Finding.query.get(finding_id)
        if not finding:
            logger.warning(f"Finding {finding_id} not found")
            return None
        
        if finding.auto_analyzed:
            logger.debug(f"Finding {finding_id} already analyzed, skipping")
            return None
        
        from services.llm_council import analyze_with_council_sync
        
        ta_snapshot = (finding.finding_metadata or {}).get("ta_snapshot", {})
        finding_dict = finding.to_dict()
        finding_dict["ta_snapshot"] = ta_snapshot
        
        result = analyze_with_council_sync(finding_dict)
        if not result.get("ok"):
            logger.warning(f"Council not run for finding {finding_id}: {result.get('reason')}")
            return None
        
        consensus = result.get("consensus") or {}
        models = result.get("models", [])
        uncertainty_spike = result.get("uncertainty_spike", False)
        
        votes_dict = {}
        for m in models:
            if m.get("ok") and m.get("parsed"):
                votes_dict[m["model"]] = m["parsed"].get("verdict", "IGNORE")
        
        finding.consensus_action = consensus.get("verdict")
        finding.consensus_confidence = consensus.get("confidence", 0.5)
        finding.llm_votes = votes_dict
        finding.llm_disagreement = uncertainty_spike
        finding.auto_analyzed = True
        
        disagreement = 1.0 - consensus.get("confidence", 0.5) if uncertainty_spike else 0.0
        
        council_row = LLMCouncilResult(
            finding_id=finding.id,
            agent_name=finding.agent_name,
            consensus=consensus.get("verdict"),
            agreement=consensus.get("confidence", 0.5),
            uncertainty=disagreement,
            models_used=list(votes_dict.keys()),
            raw_votes=votes_dict,
            analyses=[m.get("parsed") for m in models if m.get("ok")],
            severity=finding.severity,
            confidence=finding.confidence,
            created_at=datetime.utcnow(),
        )
        db.session.add(council_row)
        
        if uncertainty_spike:
            ue = UncertaintyEvent(
                label="llm_disagreement",
                score=disagreement,
                spike=True,
                disagreement=disagreement,
                votes=votes_dict,
                active_regime=active_regime,
                cadence_multiplier=0.7,
                decay_multiplier=0.8,
            )
            db.session.add(ue)
            logger.info(f"Uncertainty spike triggered for finding {finding_id}")
        
        _update_agent_council_stats(
            agent=finding.agent_name,
            regime=active_regime or "unknown",
            verdict=consensus.get("verdict", "IGNORE"),
        )
        
        if (
            consensus.get("verdict") == "ACT"
            and consensus.get("confidence", 0.0) >= ACT_THRESHOLD
        ):
            base_conf = finding.confidence or 0.5
            finding.confidence = min(1.0, base_conf + 0.10)
            logger.info(f"Boosted finding {finding_id} confidence: {base_conf:.2f} -> {finding.confidence:.2f}")
        
        db.session.commit()
        
        logger.info(f"Council completed for finding {finding_id}: {consensus.get('verdict')} (confidence={consensus.get('confidence', 0.5):.2f})")
        return result
        
    except Exception as e:
        logger.error(f"LLM council runner error for finding {finding_id}: {e}")
        db.session.rollback()
        return None


def _update_agent_council_stats(agent: str, regime: str, verdict: str):
    """
    Update per-agent per-regime council voting stats.
    Used for fail-first detection - agents with high ignore rates get penalized.
    """
    try:
        stat = (
            AgentCouncilStat.query
            .filter_by(agent_name=agent, regime=regime)
            .first()
        )
        
        if not stat:
            stat = AgentCouncilStat(
                agent_name=agent,
                regime=regime,
                votes_act=0,
                votes_watch=0,
                votes_ignore=0,
            )
            db.session.add(stat)
        
        if verdict == "ACT":
            stat.votes_act += 1
        elif verdict == "WATCH":
            stat.votes_watch += 1
        else:
            stat.votes_ignore += 1
            stat.last_ignore_ts = datetime.utcnow()
            if not stat.first_failure_ts:
                stat.first_failure_ts = stat.last_ignore_ts
        
        stat.last_updated = datetime.utcnow()
        
    except Exception as e:
        logger.error(f"Failed to update agent council stats: {e}")


def run_council_on_critical_findings(
    agent_name: str,
    active_regime: Optional[str] = None,
    limit: int = 10
):
    """
    Run council on recent critical findings from an agent.
    Called by scheduler after agent runs.
    """
    try:
        recent = (
            Finding.query
            .filter_by(agent_name=agent_name)
            .filter(Finding.severity == "critical")
            .filter(Finding.auto_analyzed == False)
            .order_by(Finding.timestamp.desc())
            .limit(limit)
            .all()
        )
        
        for finding in recent:
            run_llm_council_for_finding(finding.id, active_regime)
            
    except Exception as e:
        logger.error(f"Batch council run error for {agent_name}: {e}")


def send_act_alert_if_needed(finding: Finding) -> bool:
    """
    Send email alert if finding has ACT consensus and wasn't already alerted.
    Returns True if alert was sent.
    """
    try:
        if finding.alerted:
            return False
        
        if finding.consensus_action != "ACT":
            return False
        
        if (finding.consensus_confidence or 0) < 0.65:
            return False
        
        from notifiers.email_meta import send_critical_finding_alert
        
        consensus = {
            "action": finding.consensus_action,
            "confidence": finding.consensus_confidence,
            "votes": finding.llm_votes,
        }
        
        if send_critical_finding_alert(finding, consensus):
            finding.alerted = True
            db.session.commit()
            logger.info(f"ACT alert sent for finding {finding.id}")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Failed to send ACT alert for finding {finding.id}: {e}")
        return False


def get_fail_first_agents(regime: str, threshold: float = 0.3) -> list:
    """
    Get agents with high ignore rates in a specific regime.
    Used for substitution logic and penalty application.
    """
    try:
        stats = (
            AgentCouncilStat.query
            .filter_by(regime=regime)
            .filter(AgentCouncilStat.votes_ignore > 0)
            .all()
        )
        
        failing = []
        for stat in stats:
            if stat.ignore_rate >= threshold and stat.total_votes >= 3:
                failing.append({
                    "agent": stat.agent_name,
                    "ignore_rate": stat.ignore_rate,
                    "total_votes": stat.total_votes,
                    "first_failure": stat.first_failure_ts.isoformat() if stat.first_failure_ts else None,
                })
        
        return sorted(failing, key=lambda x: -x["ignore_rate"])
        
    except Exception as e:
        logger.error(f"Failed to get fail-first agents: {e}")
        return []
