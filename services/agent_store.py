import hashlib
import json
from datetime import datetime
from typing import Optional, Dict, Any
from models import db

class Proposal(db.Model):
    __tablename__ = 'proposals'
    id = db.Column(db.String(64), primary_key=True)
    created_at = db.Column(db.String(32), nullable=False)
    branch = db.Column(db.String(128), nullable=False)
    title = db.Column(db.String(256), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    rationale = db.Column(db.Text, nullable=False)
    unified_diff = db.Column(db.Text, nullable=False)
    overall_risk = db.Column(db.Float, nullable=False)
    file_risk_json = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(32), nullable=False, default='PROPOSED')
    reject_reason = db.Column(db.Text)

class Vote(db.Model):
    __tablename__ = 'votes'
    id = db.Column(db.Integer, primary_key=True)
    proposal_id = db.Column(db.String(64), db.ForeignKey('proposals.id'), nullable=False)
    created_at = db.Column(db.String(32), nullable=False)
    agent_name = db.Column(db.String(32), nullable=False)
    vote = db.Column(db.String(16), nullable=False)
    confidence = db.Column(db.Float, nullable=False)
    notes = db.Column(db.Text, nullable=False)

class Rejection(db.Model):
    __tablename__ = 'rejections'
    diff_hash = db.Column(db.String(64), primary_key=True)
    created_at = db.Column(db.String(32), nullable=False)
    reason = db.Column(db.Text, nullable=False)


def _now():
    return datetime.utcnow().isoformat() + "Z"


def hash_diff(unified_diff: str) -> str:
    return hashlib.sha256(unified_diff.encode("utf-8")).hexdigest()


def store_proposal(*, pid: str, branch: str, title: str, summary: str, rationale: str,
                   unified_diff: str, overall_risk: float, file_risk: Dict[str, float]) -> str:
    p = Proposal(
        id=pid,
        created_at=_now(),
        branch=branch,
        title=title,
        summary=summary,
        rationale=rationale,
        unified_diff=unified_diff,
        overall_risk=float(overall_risk),
        file_risk_json=json.dumps(file_risk),
        status='PROPOSED'
    )
    db.session.add(p)
    db.session.commit()
    return pid


def get_proposal(pid: str) -> Optional[Dict[str, Any]]:
    p = Proposal.query.get(pid)
    if not p:
        return None
    return {
        "id": p.id,
        "created_at": p.created_at,
        "branch": p.branch,
        "title": p.title,
        "summary": p.summary,
        "rationale": p.rationale,
        "unified_diff": p.unified_diff,
        "overall_risk": p.overall_risk,
        "file_risk": json.loads(p.file_risk_json),
        "status": p.status,
        "reject_reason": p.reject_reason
    }


def list_proposals(limit: int = 50):
    rows = Proposal.query.order_by(Proposal.created_at.desc()).limit(limit).all()
    return [{
        "id": r.id,
        "created_at": r.created_at,
        "branch": r.branch,
        "title": r.title,
        "overall_risk": r.overall_risk,
        "status": r.status
    } for r in rows]


def add_vote(proposal_id: str, agent_name: str, vote: str, confidence: float, notes: str):
    v = Vote(
        proposal_id=proposal_id,
        created_at=_now(),
        agent_name=agent_name,
        vote=vote,
        confidence=float(confidence),
        notes=notes
    )
    db.session.add(v)
    db.session.commit()


def get_votes(proposal_id: str):
    rows = Vote.query.filter_by(proposal_id=proposal_id).order_by(Vote.created_at.asc()).all()
    return [{
        "created_at": r.created_at,
        "agent_name": r.agent_name,
        "vote": r.vote,
        "confidence": r.confidence,
        "notes": r.notes
    } for r in rows]


def reject_proposal(pid: str, reason: str):
    p = Proposal.query.get(pid)
    if not p:
        return
    h = hash_diff(p.unified_diff)
    p.status = 'REJECTED'
    p.reject_reason = reason
    
    existing = Rejection.query.get(h)
    if existing:
        existing.reason = reason
        existing.created_at = _now()
    else:
        r = Rejection(diff_hash=h, created_at=_now(), reason=reason)
        db.session.add(r)
    db.session.commit()


def mark_status(pid: str, status: str):
    p = Proposal.query.get(pid)
    if p:
        p.status = status
        db.session.commit()


def previously_rejected_reason(unified_diff: str) -> Optional[str]:
    h = hash_diff(unified_diff)
    r = Rejection.query.get(h)
    return r.reason if r else None
