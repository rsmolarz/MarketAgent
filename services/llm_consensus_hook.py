"""
LLM Consensus Hook for TA Integration
Compares TA signals with LLM council verdicts to boost or spike uncertainty
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

UNCERTAINTY_SPIKE_THRESHOLD = 0.55
ACT_THRESHOLD = 0.60


def extract_ta_snapshot_from_finding(finding) -> dict:
    """Extract TA snapshot from finding metadata"""
    meta = getattr(finding, "finding_metadata", None) or {}
    if isinstance(meta, dict):
        return meta.get("ta_snapshot") or meta.get("ta") or {}
    return {}


def should_spike_uncertainty(consensus: dict) -> bool:
    """Check if council disagreement should trigger uncertainty spike"""
    disagreement = consensus.get("disagreement", 0.0)
    ta_alignment = consensus.get("ta_alignment_mode", "unknown")
    return (disagreement >= UNCERTAINTY_SPIKE_THRESHOLD) or (ta_alignment == "conflict")


def apply_confidence_boost(finding, consensus: dict) -> bool:
    """
    Boost finding confidence if TA aligns and council says ACT
    Returns True if boost was applied
    """
    try:
        if consensus.get("verdict") != "ACT":
            return False
        if consensus.get("consensus_strength", 0) < ACT_THRESHOLD:
            return False
        if consensus.get("ta_alignment_mode") != "aligned":
            return False

        base = float(getattr(finding, "confidence", 0.5) or 0.5)
        boosted = min(base + 0.10, 1.0)
        setattr(finding, "confidence", boosted)
        logger.info(f"Boosted finding {finding.id} confidence: {base:.2f} -> {boosted:.2f}")
        return True
    except Exception as e:
        logger.warning(f"Confidence boost failed: {e}")
        return False


def run_ta_council_hook(db, Finding, finding_id: int) -> Optional[Dict[str, Any]]:
    """
    Run LLM council on a finding with its TA snapshot
    Persists result and triggers uncertainty if needed
    """
    try:
        finding = Finding.query.get(finding_id)
        if not finding:
            return None

        from services.llm_council import run_council
        
        finding_dict = {
            "id": finding.id,
            "title": finding.title,
            "description": getattr(finding, "description", ""),
            "severity": finding.severity,
            "confidence": finding.confidence,
            "symbol": finding.symbol,
            "agent_name": finding.agent_name,
            "timestamp": finding.timestamp.isoformat() if finding.timestamp else None,
        }

        ta_snapshot = extract_ta_snapshot_from_finding(finding)
        result = run_council(finding_dict, ta_snapshot)
        
        if not result.get("ok"):
            logger.warning(f"Council not run for finding {finding_id}: {result.get('reason')}")
            return None

        consensus = result.get("consensus", {})
        
        from models import LLMCouncilResult, UncertaintyEvent
        from services.llm_council_persistence import persist_council_result
        
        persist_council_result(
            agent_name=finding.agent_name,
            symbol=finding.symbol,
            finding_id=finding_id,
            consensus=consensus.get("verdict", "WATCH"),
            agreement=consensus.get("consensus_strength", 0.5),
            models_used=["claude", "gpt", "gemini"],
            votes=result.get("votes", []),
            analyses=[v.get("data", {}) for v in result.get("votes", [])],
            metadata={
                "ta_alignment": consensus.get("ta_alignment_mode"),
                "disagreement": consensus.get("disagreement"),
                "mean_confidence": consensus.get("mean_confidence"),
            }
        )
        db.session.commit()
        
        if should_spike_uncertainty(consensus):
            from meta.uncertainty import record_uncertainty_event
            record_uncertainty_event(
                agent_name=finding.agent_name,
                event_type="llm_ta_conflict",
                severity=consensus.get("disagreement", 0.5),
                details={
                    "finding_id": finding_id,
                    "ta_alignment": consensus.get("ta_alignment_mode"),
                    "council_verdict": consensus.get("verdict"),
                }
            )
            db.session.commit()
            logger.info(f"Uncertainty spike triggered for finding {finding_id}")
        
        if apply_confidence_boost(finding, consensus):
            db.session.commit()
        
        return result

    except Exception as e:
        logger.error(f"TA council hook error for finding {finding_id}: {e}")
        return None


def run_ta_council_for_critical_findings(db, Finding, agent_name: str, limit: int = 10):
    """Run council hook on recent critical findings from an agent"""
    try:
        recent = (
            Finding.query
            .filter_by(agent_name=agent_name)
            .filter_by(severity="critical")
            .order_by(Finding.timestamp.desc())
            .limit(limit)
            .all()
        )
        
        for finding in recent:
            run_ta_council_hook(db, Finding, finding.id)
            
    except Exception as e:
        logger.error(f"Batch TA council hook error: {e}")
