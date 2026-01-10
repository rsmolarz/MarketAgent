from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from flask_dance.consumer.storage.sqla import OAuthConsumerMixin
from sqlalchemy import (
    Integer,
    String,
    DateTime,
    Text,
    Float,
    Boolean,
    JSON,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column

# =========================================================
# Global SQLAlchemy instance
# =========================================================
db = SQLAlchemy()

# =========================================================
# Replit Auth Models (DO NOT REMOVE)
# =========================================================

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    first_name: Mapped[str | None] = mapped_column(String, nullable=True)
    last_name: Mapped[str | None] = mapped_column(String, nullable=True)
    profile_image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "profile_image_url": self.profile_image_url,
            "is_admin": self.is_admin,
            "created_at": self.created_at.isoformat(),
        }


class OAuth(OAuthConsumerMixin, db.Model):
    __tablename__ = "oauth"

    user_id = mapped_column(String, db.ForeignKey(User.id))
    user = db.relationship(User)
    browser_session_key: Mapped[str | None] = mapped_column(String(64), nullable=True)

class Whitelist(db.Model):
    __tablename__ = "whitelist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    added_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    added_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "added_by": self.added_by,
            "added_at": self.added_at.isoformat(),
            "notes": self.notes,
        }

# =========================================================
# Core Platform Models
# =========================================================

class Finding(db.Model):
    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)

    finding_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    symbol: Mapped[str | None] = mapped_column(String(20), nullable=True)
    market_type: Mapped[str | None] = mapped_column(String(20), nullable=True)

    consensus_action: Mapped[str | None] = mapped_column(String(16), nullable=True)
    consensus_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    llm_votes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    llm_disagreement: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_analyzed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    alerted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ta_regime: Mapped[str | None] = mapped_column(String(32), nullable=True)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    regime: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    drawdown: Mapped[float | None] = mapped_column(Float, nullable=True)
    capital_gate: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "agent_name": self.agent_name,
            "timestamp": self.timestamp.isoformat(),
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "confidence": self.confidence,
            "metadata": self.finding_metadata,
            "symbol": self.symbol,
            "market_type": self.market_type,
            "consensus_action": self.consensus_action,
            "consensus_confidence": self.consensus_confidence,
            "llm_votes": self.llm_votes,
            "llm_disagreement": self.llm_disagreement,
            "auto_analyzed": self.auto_analyzed,
            "alerted": self.alerted,
            "ta_regime": self.ta_regime,
            "analyzed_at": self.analyzed_at.isoformat() if self.analyzed_at else None,
            "regime": self.regime,
            "drawdown": self.drawdown,
            "capital_gate": self.capital_gate,
        }


class AgentStatus(db.Model):
    __tablename__ = "agent_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_run: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    run_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    schedule_interval: Mapped[int] = mapped_column(
        Integer, default=60, nullable=False
    )

    def to_dict(self):
        return {
            "agent_name": self.agent_name,
            "is_active": self.is_active,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "run_count": self.run_count,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "schedule_interval": self.schedule_interval,
        }


class MarketData(db.Model):
    __tablename__ = "market_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    price: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_cap: Mapped[float | None] = mapped_column(Float, nullable=True)

    data_source: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    def to_dict(self):
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "price": self.price,
            "volume": self.volume,
            "market_cap": self.market_cap,
            "data_source": self.data_source,
            "raw_data": self.raw_data,
        }


class UncertaintyEvent(db.Model):
    __tablename__ = "uncertainty_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True, nullable=False
    )

    label: Mapped[str] = mapped_column(String(32), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    spike: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    disagreement: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    votes: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    active_regime: Mapped[str | None] = mapped_column(String(64), nullable=True)
    regime_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    cadence_multiplier: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    decay_multiplier: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "label": self.label,
            "score": self.score,
            "spike": self.spike,
            "disagreement": self.disagreement,
            "votes": self.votes,
            "active_regime": self.active_regime,
            "regime_confidence": self.regime_confidence,
            "cadence_multiplier": self.cadence_multiplier,
            "decay_multiplier": self.decay_multiplier,
        }


Index("ix_uncertainty_event_ts", UncertaintyEvent.timestamp)


class AgentSubstitution(db.Model):
    """
    Records agent substitutions for explainability and analysis.
    Logged when an agent is replaced due to decay in a specific regime.
    """
    __tablename__ = "agent_substitution"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True, nullable=False
    )
    
    regime: Mapped[str] = mapped_column(String(32), nullable=False)
    from_agent: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    to_agent: Mapped[str] = mapped_column(String(64), nullable=False)
    
    from_decay: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    to_decay: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    
    confidence: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    
    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "regime": self.regime,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "from_decay": self.from_decay,
            "to_decay": self.to_decay,
            "confidence": self.confidence,
            "reason": self.reason,
        }


Index("ix_agent_substitution_regime", AgentSubstitution.regime)


class ApprovalEvent(db.Model):
    """
    Records approval events for agent proposals, configuration changes,
    and other actions requiring admin review.
    """
    __tablename__ = "approval_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, default="proposal")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    
    proposal_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    agent_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    event_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    
    def to_dict(self):
        return {
            "id": self.id,
            "event_type": self.event_type,
            "description": self.description,
            "status": self.status,
            "proposal_id": self.proposal_id,
            "agent_name": self.agent_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewed_by": self.reviewed_by,
            "metadata": self.event_metadata,
        }


Index("ix_approval_event_status", ApprovalEvent.status)


class AgentCouncilStat(db.Model):
    """
    Tracks council voting outcomes per agent per regime.
    Used for 'fail-first' detection - agents with high ignore rates
    under uncertainty get weight penalties.
    """
    __tablename__ = "agent_council_stat"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    regime: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown", index=True)

    votes_act: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    votes_watch: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    votes_ignore: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    first_failure_ts: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_ignore_ts: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("agent_name", "regime", name="uq_agent_council_regime"),
    )

    @property
    def total_votes(self) -> int:
        return self.votes_act + self.votes_watch + self.votes_ignore

    @property
    def ignore_rate(self) -> float:
        total = self.total_votes
        return self.votes_ignore / total if total > 0 else 0.0

    def to_dict(self):
        return {
            "id": self.id,
            "agent_name": self.agent_name,
            "regime": self.regime,
            "votes_act": self.votes_act,
            "votes_watch": self.votes_watch,
            "votes_ignore": self.votes_ignore,
            "total_votes": self.total_votes,
            "ignore_rate": round(self.ignore_rate, 3),
            "first_failure_ts": self.first_failure_ts.isoformat() if self.first_failure_ts else None,
            "last_ignore_ts": self.last_ignore_ts.isoformat() if self.last_ignore_ts else None,
            "last_updated": self.last_updated.isoformat(),
        }


class LLMModelRegimeStat(db.Model):
    __tablename__ = "llm_model_regime_stat"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    regime: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    n: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    last_updated: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("model", "regime", name="uq_model_regime"),
    )

    @property
    def accuracy(self) -> float:
        return self.correct / self.n if self.n else 0.5

    def to_dict(self):
        return {
            "id": self.id,
            "model": self.model,
            "regime": self.regime,
            "n": self.n,
            "correct": self.correct,
            "accuracy": self.accuracy,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }


class DistressedDeal(db.Model):
    """
    Tracks distressed property deals through the pipeline.
    Stage progression: screened → underwritten → LOI → closed
    """
    __tablename__ = "distressed_deals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    property_address: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(10), nullable=True)
    zip_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    
    property_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    distress_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    asking_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    offer_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    stage: Mapped[str] = mapped_column(String(20), nullable=False, default="screened", index=True)
    stage_history: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    
    finding_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    source_agent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    ic_memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    ic_memo_generated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    underwriting_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    underwriting_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    loi_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    loi_accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    crm_synced: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    crm_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    crm_external_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    deal_room_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    assigned_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    deal_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    VALID_STAGES = ["screened", "underwritten", "loi", "closed", "dead"]
    STAGE_ORDER = {"screened": 1, "underwritten": 2, "loi": 3, "closed": 4, "dead": 0}

    def progress_stage(self, new_stage: str, notes: str = None) -> bool:
        """
        Progress deal to next stage. Returns True if successful.
        """
        if new_stage not in self.VALID_STAGES:
            return False
        
        if new_stage == "dead":
            pass
        elif self.STAGE_ORDER.get(new_stage, 0) <= self.STAGE_ORDER.get(self.stage, 0):
            return False
        
        old_stage = self.stage
        self.stage = new_stage
        
        history = self.stage_history or []
        history.append({
            "from": old_stage,
            "to": new_stage,
            "at": datetime.utcnow().isoformat(),
            "notes": notes
        })
        self.stage_history = history
        
        if new_stage == "loi":
            self.loi_sent_at = datetime.utcnow()
        elif new_stage == "closed":
            self.closed_at = datetime.utcnow()
        
        return True

    def to_dict(self):
        return {
            "id": self.id,
            "property_address": self.property_address,
            "city": self.city,
            "state": self.state,
            "zip_code": self.zip_code,
            "property_type": self.property_type,
            "distress_type": self.distress_type,
            "asking_price": self.asking_price,
            "estimated_value": self.estimated_value,
            "offer_price": self.offer_price,
            "final_price": self.final_price,
            "stage": self.stage,
            "stage_history": self.stage_history,
            "finding_id": self.finding_id,
            "source_agent": self.source_agent,
            "ic_memo": self.ic_memo,
            "ic_memo_generated_at": self.ic_memo_generated_at.isoformat() if self.ic_memo_generated_at else None,
            "underwriting_notes": self.underwriting_notes,
            "underwriting_score": self.underwriting_score,
            "loi_sent_at": self.loi_sent_at.isoformat() if self.loi_sent_at else None,
            "loi_accepted_at": self.loi_accepted_at.isoformat() if self.loi_accepted_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "crm_synced": self.crm_synced,
            "crm_sync_at": self.crm_sync_at.isoformat() if self.crm_sync_at else None,
            "crm_external_id": self.crm_external_id,
            "deal_room_url": self.deal_room_url,
            "assigned_to": self.assigned_to,
            "metadata": self.deal_metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


Index("ix_distressed_deal_stage", DistressedDeal.stage)
Index("ix_distressed_deal_created", DistressedDeal.created_at)


class DealValuation(db.Model):
    """Pricing bands and recovery modeling for distressed deals."""
    __tablename__ = "deal_valuations"

    deal_id: Mapped[int] = mapped_column(
        Integer, db.ForeignKey("distressed_deals.id", ondelete="CASCADE"), primary_key=True
    )
    
    zestimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    rent_zestimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    distressed_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    recovery_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    discount_to_zestimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    recovery_multiple: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    valuation_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    valuation_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    deal = db.relationship("DistressedDeal", backref=db.backref("valuation", uselist=False))

    def compute_pricing_bands(self, zestimate: float, discount_low: float = 0.55, discount_high: float = 0.75):
        """Compute distressed pricing bands from Zestimate."""
        self.zestimate = zestimate
        mid_discount = (discount_low + discount_high) / 2
        self.distressed_price = zestimate * mid_discount
        self.recovery_value = zestimate * 0.95
        self.discount_to_zestimate = 1.0 - mid_discount
        if self.distressed_price and self.distressed_price > 0:
            self.recovery_multiple = self.recovery_value / self.distressed_price
        self.valuation_date = datetime.utcnow()

    def to_dict(self):
        return {
            "deal_id": self.deal_id,
            "zestimate": self.zestimate,
            "rent_zestimate": self.rent_zestimate,
            "distressed_price": self.distressed_price,
            "recovery_value": self.recovery_value,
            "discount_to_zestimate": self.discount_to_zestimate,
            "recovery_multiple": self.recovery_multiple,
            "confidence": self.confidence,
            "valuation_source": self.valuation_source,
            "valuation_date": self.valuation_date.isoformat() if self.valuation_date else None,
        }


class ICVote(db.Model):
    """IC voting tracking for human vs AI decisions with override logic."""
    __tablename__ = "ic_votes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    deal_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("distressed_deals.id"), index=True, nullable=False)
    
    voter: Mapped[str] = mapped_column(String(64), nullable=False)
    voter_type: Mapped[str] = mapped_column(String(16), default="human", nullable=False)
    
    vote: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    is_override: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    deal = db.relationship("DistressedDeal", backref=db.backref("ic_votes", lazy="dynamic"))

    def to_dict(self):
        return {
            "id": self.id,
            "deal_id": self.deal_id,
            "voter": self.voter,
            "voter_type": self.voter_type,
            "vote": self.vote,
            "confidence": self.confidence,
            "notes": self.notes,
            "is_override": self.is_override,
            "override_reason": self.override_reason,
            "created_at": self.created_at.isoformat(),
        }


Index("ix_ic_vote_deal", ICVote.deal_id)
Index("ix_ic_vote_voter", ICVote.voter)


class LLMCouncilResult(db.Model):
    __tablename__ = "llm_council_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    finding_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    agent_name: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)

    consensus: Mapped[str | None] = mapped_column(String(16), nullable=True)
    agreement: Mapped[float | None] = mapped_column(Float, nullable=True)
    uncertainty: Mapped[float | None] = mapped_column(Float, nullable=True)

    models_used: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    raw_votes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    analyses: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    severity: Mapped[str | None] = mapped_column(String(16), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "finding_id": self.finding_id,
            "agent": self.agent_name,
            "consensus": self.consensus,
            "agreement": self.agreement,
            "uncertainty": self.uncertainty,
            "models_used": self.models_used,
            "severity": self.severity,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
