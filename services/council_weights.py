import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def get_model_weight(model: str, regime: str) -> float:
    """
    Get regime-specific weight for LLM model.
    
    Args:
        model: model name ('gpt', 'claude', 'gemini')
        regime: current regime ('risk_on', 'risk_off', 'volatile', 'calm')
    
    Returns:
        Weight multiplier (0.5-1.5 based on historical accuracy)
    """
    try:
        from models import LLMModelRegimeStat
        s = LLMModelRegimeStat.query.filter_by(model=model, regime=regime).first()
        if not s:
            return 1.0
        return 0.5 + s.accuracy
    except Exception as e:
        logger.debug(f"Could not get model weight: {e}")
        return 1.0


def update_model_stat(model: str, regime: str, correct: bool) -> None:
    """
    Update model performance statistics for a regime.
    
    Args:
        model: model name
        regime: regime label
        correct: whether the model's prediction was correct
    """
    try:
        from models import db, LLMModelRegimeStat
        
        s = LLMModelRegimeStat.query.filter_by(model=model, regime=regime).first()
        if not s:
            s = LLMModelRegimeStat(model=model, regime=regime)
            s.n = 0
            s.correct = 0
            db.session.add(s)
        s.n += 1
        if correct:
            s.correct += 1
        db.session.commit()
        logger.debug(f"Updated {model}/{regime}: n={s.n}, correct={s.correct}")
    except Exception as e:
        logger.error(f"Failed to update model stat: {e}")


def get_all_model_stats() -> list:
    """Get all model regime statistics."""
    try:
        from models import LLMModelRegimeStat
        stats = LLMModelRegimeStat.query.all()
        return [
            {
                "model": s.model,
                "regime": s.regime,
                "n": s.n,
                "correct": s.correct,
                "accuracy": s.accuracy
            }
            for s in stats
        ]
    except Exception as e:
        logger.error(f"Failed to get model stats: {e}")
        return []


def evaluate_council_outcome(votes: dict, actual_outcome: str, regime: str) -> None:
    """
    Evaluate council votes against actual outcome and update stats.
    
    Args:
        votes: {model: {"vote": "ACT/WATCH/IGNORE", "confidence": 0-1}}
        actual_outcome: "positive" or "negative" based on realized PnL
        regime: regime at time of prediction
    """
    for model, vote_data in votes.items():
        vote = (vote_data.get("vote") or "IGNORE").upper()
        
        if actual_outcome == "positive":
            correct = vote == "ACT"
        else:
            correct = vote == "IGNORE"
        
        update_model_stat(model, regime, correct)
