import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


def _get_models():
    """Lazy import to avoid circular imports."""
    from models import AgentMemory, db
    return AgentMemory, db


def get_recent_builder_rejections(limit: int = 10) -> List[str]:
    """Get recent rejection reasons to help Builder agent avoid repeating mistakes."""
    AgentMemory, _ = _get_models()
    rows = (AgentMemory.query
            .filter_by(scope="BUILDER", key="previous_rejection_reason")
            .order_by(AgentMemory.created_at.desc())
            .limit(limit)
            .all())
    return [r.value for r in rows]


def store_rejection_memory(reason: str, proposal_id: Optional[int] = None) -> None:
    """Store a rejection reason in agent memory."""
    AgentMemory, db = _get_models()
    memory = AgentMemory(
        scope="BUILDER",
        key="previous_rejection_reason",
        value=reason,
        proposal_id=proposal_id
    )
    db.session.add(memory)
    db.session.commit()


def store_memory(scope: str, key: str, value: str, proposal_id: Optional[int] = None) -> None:
    """Store a generic memory entry."""
    AgentMemory, db = _get_models()
    memory = AgentMemory(
        scope=scope,
        key=key,
        value=value,
        proposal_id=proposal_id
    )
    db.session.add(memory)
    db.session.commit()


def get_memories_by_scope(scope: str, limit: int = 50) -> List[dict]:
    """Get all memories for a given scope."""
    AgentMemory, _ = _get_models()
    rows = (AgentMemory.query
            .filter_by(scope=scope)
            .order_by(AgentMemory.created_at.desc())
            .limit(limit)
            .all())
    return [r.to_dict() for r in rows]


def get_memories_by_key(key: str, limit: int = 50) -> List[dict]:
    """Get all memories with a specific key."""
    AgentMemory, _ = _get_models()
    rows = (AgentMemory.query
            .filter_by(key=key)
            .order_by(AgentMemory.created_at.desc())
            .limit(limit)
            .all())
    return [r.to_dict() for r in rows]


def format_rejection_context(rejections: List[str]) -> str:
    """Format rejection reasons for injection into Builder prompt."""
    if not rejections:
        return ""
    
    lines = ["PREVIOUSLY REJECTED REASONS (avoid repeating these):"]
    for i, reason in enumerate(rejections, 1):
        lines.append(f"  {i}. {reason}")
    return "\n".join(lines)


def clear_memories_for_proposal(proposal_id: int) -> int:
    """Delete all memories associated with a proposal. Returns count deleted."""
    AgentMemory, db = _get_models()
    count = AgentMemory.query.filter_by(proposal_id=proposal_id).delete()
    db.session.commit()
    return count
