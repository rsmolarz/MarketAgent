from datetime import datetime
from app import db
from sqlalchemy import Integer, String, DateTime, Text, Float, Boolean, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from flask_dance.consumer.storage.sqla import OAuthConsumerMixin
from flask_login import UserMixin


# (IMPORTANT) This table is mandatory for Replit Auth, don't drop it.
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.String, primary_key=True)
    email = db.Column(db.String, unique=True, nullable=True)
    first_name = db.Column(db.String, nullable=True)
    last_name = db.Column(db.String, nullable=True)
    profile_image_url = db.Column(db.String, nullable=True)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime,
                           default=datetime.now,
                           onupdate=datetime.now)
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'profile_image_url': self.profile_image_url,
            'is_admin': self.is_admin,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# (IMPORTANT) This table is mandatory for Replit Auth, don't drop it.
class OAuth(OAuthConsumerMixin, db.Model):
    user_id = db.Column(db.String, db.ForeignKey(User.id))
    browser_session_key = db.Column(db.String, nullable=False)
    user = db.relationship(User)

    __table_args__ = (UniqueConstraint(
        'user_id',
        'browser_session_key',
        'provider',
        name='uq_user_browser_session_key_provider',
    ),)


class Whitelist(db.Model):
    """Whitelist table - only users with matching email can access the platform"""
    __tablename__ = 'whitelist'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    added_by: Mapped[str] = mapped_column(String(255), nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'added_by': self.added_by,
            'added_at': self.added_at.isoformat() if self.added_at else None,
            'notes': self.notes
        }

class Finding(db.Model):
    __tablename__ = 'findings'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default='medium', nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    finding_metadata: Mapped[dict] = mapped_column(JSON, nullable=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=True)
    market_type: Mapped[str] = mapped_column(String(20), nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'agent_name': self.agent_name,
            'timestamp': self.timestamp.isoformat(),
            'title': self.title,
            'description': self.description,
            'severity': self.severity,
            'confidence': self.confidence,
            'metadata': self.finding_metadata,
            'symbol': self.symbol,
            'market_type': self.market_type
        }

class AgentStatus(db.Model):
    __tablename__ = 'agent_status'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_run: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    run_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str] = mapped_column(Text, nullable=True)
    schedule_interval: Mapped[int] = mapped_column(Integer, default=60, nullable=False)  # minutes
    
    def to_dict(self):
        return {
            'id': self.id,
            'agent_name': self.agent_name,
            'is_active': self.is_active,
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'run_count': self.run_count,
            'error_count': self.error_count,
            'last_error': self.last_error,
            'schedule_interval': self.schedule_interval
        }

class MarketData(db.Model):
    __tablename__ = 'market_data'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=True)
    market_cap: Mapped[float] = mapped_column(Float, nullable=True)
    data_source: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_data: Mapped[dict] = mapped_column(JSON, nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'price': self.price,
            'volume': self.volume,
            'market_cap': self.market_cap,
            'data_source': self.data_source,
            'raw_data': self.raw_data
        }
