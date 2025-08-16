from datetime import datetime
from app import db
from sqlalchemy import Integer, String, DateTime, Text, Float, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column

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
