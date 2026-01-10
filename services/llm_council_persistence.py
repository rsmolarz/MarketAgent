import logging
from models import db, LLMCouncilResult

logger = logging.getLogger(__name__)


def persist_council_result(finding, council_result: dict) -> LLMCouncilResult | None:
    try:
        record = LLMCouncilResult(
            finding_id=finding.id,
            agent_name=finding.agent_name,
            consensus=council_result.get("consensus"),
            agreement=council_result.get("agreement"),
            uncertainty=council_result.get("uncertainty"),
            models_used=council_result.get("models_used"),
            raw_votes=council_result.get("votes"),
            analyses=council_result.get("analyses"),
            severity=finding.severity,
            confidence=finding.confidence
        )

        db.session.add(record)
        db.session.commit()

        logger.info(f"Persisted council result for finding {finding.id}: consensus={record.consensus}, uncertainty={record.uncertainty}")
        return record

    except Exception as e:
        logger.error(f"Failed to persist council result for finding {finding.id}: {e}")
        db.session.rollback()
        return None


def get_agent_council_stats(agent_name: str, days: int = 30) -> dict:
    from datetime import datetime, timedelta
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    results = LLMCouncilResult.query.filter(
        LLMCouncilResult.agent_name == agent_name,
        LLMCouncilResult.created_at >= cutoff
    ).all()
    
    if not results:
        return {
            "agent_name": agent_name,
            "count": 0,
            "mean_agreement": None,
            "mean_uncertainty": None,
            "consensus_distribution": {}
        }
    
    agreements = [r.agreement for r in results if r.agreement is not None]
    uncertainties = [r.uncertainty for r in results if r.uncertainty is not None]
    
    consensus_counts = {"ACT": 0, "WATCH": 0, "IGNORE": 0}
    for r in results:
        if r.consensus in consensus_counts:
            consensus_counts[r.consensus] += 1
    
    return {
        "agent_name": agent_name,
        "count": len(results),
        "mean_agreement": round(sum(agreements) / len(agreements), 3) if agreements else None,
        "mean_uncertainty": round(sum(uncertainties) / len(uncertainties), 3) if uncertainties else None,
        "consensus_distribution": consensus_counts
    }


def get_all_council_stats(days: int = 30) -> list:
    from datetime import datetime, timedelta
    from sqlalchemy import func
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    stats = db.session.query(
        LLMCouncilResult.agent_name,
        func.count(LLMCouncilResult.id).label("count"),
        func.avg(LLMCouncilResult.agreement).label("mean_agreement"),
        func.avg(LLMCouncilResult.uncertainty).label("mean_uncertainty")
    ).filter(
        LLMCouncilResult.created_at >= cutoff
    ).group_by(
        LLMCouncilResult.agent_name
    ).all()
    
    return [
        {
            "agent_name": s.agent_name,
            "count": s.count,
            "mean_agreement": round(float(s.mean_agreement), 3) if s.mean_agreement else None,
            "mean_uncertainty": round(float(s.mean_uncertainty), 3) if s.mean_uncertainty else None
        }
        for s in stats
    ]
