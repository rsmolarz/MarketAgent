"""
Triple-confirmation Gate + Auto-email on Critical

For a finding:
1. Compute TA confirmation for that symbol
2. Run 3-LLM council consensus (ACT/WATCH/IGNORE)
3. Combine with agent severity/confidence

If critical and consensus == ACT and TA agrees → auto-email whitelist
"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def should_auto_alert(finding, council: dict, ta: dict) -> bool:
    """Check if finding passes triple-confirmation gate."""
    if (getattr(finding, 'severity', '') or '').lower() != 'critical':
        return False
    if council.get('consensus') != 'ACT':
        return False
    if ta.get('vote') != 'ACT':
        return False
    return True


def auto_analyze_and_alert(finding_id: int, force: bool = False) -> Dict[str, Any]:
    """
    Run triple-confirmation analysis on a finding.
    
    Args:
        finding_id: ID of the finding to analyze
        force: Re-analyze even if already analyzed
    
    Returns:
        Dict with analysis results and alert status
    """
    from datetime import datetime
    from models import db, Finding, Whitelist
    from services.llm_council import llm_council_analyze_finding
    from ta.ta_engine import ta_vote
    from data_sources.price_loader import load_symbol_frame
    
    try:
        from services.email_meta import send_meta_email
    except ImportError:
        send_meta_email = None
    
    f = Finding.query.get(finding_id)
    if not f:
        return {"ok": False, "reason": "finding_not_found"}

    if getattr(f, 'auto_analyzed', False) and not force:
        return {"ok": True, "reason": "already_analyzed"}

    payload = f.to_dict() if hasattr(f, 'to_dict') else {
        "id": f.id,
        "title": f.title,
        "description": f.description,
        "severity": f.severity,
        "symbol": f.symbol,
        "agent_name": f.agent_name,
        "confidence": f.confidence,
    }
    payload["agent"] = f.agent_name

    try:
        df = load_symbol_frame(f.symbol) if f.symbol else None
        ta = ta_vote(df)
    except Exception as e:
        logger.warning(f"TA analysis failed for {f.symbol}: {e}")
        ta = {"vote": "WATCH", "score": 0.5, "reason": f"error: {e}"}

    try:
        council = llm_council_analyze_finding(f)
        council_consensus = council.get("action", "WATCH")
        council_agreement = council.get("confidence", 0.5)
        council_votes = council.get("votes", {})
        council_spike = council.get("disagreement", False)
    except Exception as e:
        logger.warning(f"LLM council failed for finding {finding_id}: {e}")
        council = {"action": "WATCH", "confidence": 0.0, "votes": {}, "disagreement": True}
        council_consensus = "WATCH"
        council_agreement = 0.0
        council_votes = {}
        council_spike = True

    ta_score = ta.get("score", 0.5)
    combined_confidence = round(0.65 * float(council_agreement) + 0.35 * float(ta_score), 4)
    
    try:
        f.consensus_action = council_consensus
        f.consensus_confidence = combined_confidence
        f.llm_votes = council_votes
        f.llm_disagreement = bool(council_spike)
        f.auto_analyzed = True
        f.ta_regime = ta.get("regime") or ta.get("vote")
        f.analyzed_at = datetime.utcnow()
    except Exception as e:
        logger.warning(f"Failed to update finding fields: {e}")

    alerted = False
    council_dict = {"consensus": council_consensus, "agreement": council_agreement}
    
    if should_auto_alert(f, council_dict, ta) and not getattr(f, 'alerted', False):
        try:
            if send_meta_email:
                emails = [w.email for w in Whitelist.query.all()]
                subject = f"[ACT] {f.title} ({f.symbol or 'N/A'})"
                text = (
                    f"Critical finding confirmed by TA + LLM council\n\n"
                    f"Title: {f.title}\n"
                    f"Agent: {f.agent_name}\n"
                    f"Symbol: {f.symbol}\n"
                    f"Severity: {f.severity}\n"
                    f"Confidence: {f.confidence}\n\n"
                    f"TA: {ta}\n"
                    f"Council: {council}\n\n"
                    f"Description:\n{f.description}\n"
                )
                html = "<pre>" + text + "</pre>"
                send_meta_email(subject, text, html, to_override=emails)
                f.alerted = True
                alerted = True
                logger.info(f"Auto-alerted for finding {finding_id}")
        except Exception as e:
            logger.error(f"Failed to send auto-alert: {e}")

    try:
        db.session.commit()
    except Exception as e:
        logger.error(f"Failed to commit finding updates: {e}")
        db.session.rollback()

    return {
        "ok": True, 
        "ta": ta, 
        "council": council, 
        "alerted": alerted,
        "triple_confirmed": should_auto_alert(f, council_dict, ta)
    }


def get_triage_summary(limit: int = 50) -> Dict[str, Any]:
    """Get summary of recent auto-triage results."""
    from models import Finding
    
    try:
        findings = (
            Finding.query
            .filter(Finding.auto_analyzed == True)
            .order_by(Finding.timestamp.desc())
            .limit(limit)
            .all()
        )
        
        act_count = sum(1 for f in findings if getattr(f, 'consensus_action', '') == 'ACT')
        watch_count = sum(1 for f in findings if getattr(f, 'consensus_action', '') == 'WATCH')
        ignore_count = sum(1 for f in findings if getattr(f, 'consensus_action', '') == 'IGNORE')
        alerted_count = sum(1 for f in findings if getattr(f, 'alerted', False))
        
        return {
            "total_analyzed": len(findings),
            "act": act_count,
            "watch": watch_count,
            "ignore": ignore_count,
            "alerted": alerted_count,
        }
    except Exception as e:
        logger.error(f"Failed to get triage summary: {e}")
        return {"total_analyzed": 0, "act": 0, "watch": 0, "ignore": 0, "alerted": 0}
