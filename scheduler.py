import json
import threading
import time
import logging
from datetime import datetime
from typing import Dict, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from agents import get_agent_class
from models import AgentStatus, Finding

logger = logging.getLogger(__name__)

class AgentScheduler:
    def __init__(self, app=None):
        self.app = app
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        self.active_jobs = {}
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize with Flask app"""
        self.app = app
        with app.app_context():
            self.load_schedule()
    
    def load_schedule(self):
        """Load agent schedule from JSON file"""
        try:
            with open("agent_schedule.json", "r") as f:
                schedule_data = json.load(f)
                
            # Import db here to avoid circular import
            from app import db
            for agent_name, interval_minutes in schedule_data.items():
                # Ensure agent status exists in database
                status = AgentStatus.query.filter_by(agent_name=agent_name).first()
                if not status:
                    status = AgentStatus()
                    status.agent_name = agent_name
                    status.schedule_interval = interval_minutes
                    status.is_active = False
                    db.session.add(status)
                
                db.session.commit()
                logger.info(f"Loaded schedule for {len(schedule_data)} agents")
                
        except FileNotFoundError:
            logger.warning("agent_schedule.json not found, using default schedule")
            self.create_default_schedule()
        except Exception as e:
            logger.error(f"Error loading schedule: {e}")
            self.create_default_schedule()
    
    def create_default_schedule(self):
        """Create default schedule for all available agents"""
        default_agents = {
            "MacroWatcherAgent": 60,
            "WhaleWalletWatcherAgent": 15,
            "ArbitrageFinderAgent": 5,
            "SentimentDivergenceAgent": 30,
            "AltDataSignalAgent": 45,
            "EquityMomentumAgent": 30,
            "CryptoFundingRateAgent": 15,
            "BondStressAgent": 60
        }
        
        with open("agent_schedule.json", "w") as f:
            json.dump(default_agents, f, indent=2)
        
        # Import db here to avoid circular import
        from app import db
        for agent_name, interval in default_agents.items():
            status = AgentStatus.query.filter_by(agent_name=agent_name).first()
            if not status:
                status = AgentStatus()
                status.agent_name = agent_name
                status.schedule_interval = interval
                status.is_active = False
                db.session.add(status)
        
        db.session.commit()
    
    def start_agent(self, agent_name: str) -> bool:
        """Start scheduling an agent"""
        try:
            # Import db here to avoid circular import
            from app import db
            with self.app.app_context():
                status = AgentStatus.query.filter_by(agent_name=agent_name).first()
                if not status:
                    logger.error(f"Agent {agent_name} not found in database")
                    return False
                
                if agent_name in self.active_jobs:
                    logger.warning(f"Agent {agent_name} is already scheduled")
                    return True
                
                # Create scheduler job
                job = self.scheduler.add_job(
                    func=self._run_agent,
                    trigger=IntervalTrigger(minutes=status.schedule_interval),
                    args=[agent_name],
                    id=agent_name,
                    replace_existing=True
                )
                
                self.active_jobs[agent_name] = job
                status.is_active = True
                db.session.commit()
                
                logger.info(f"Started agent {agent_name} with {status.schedule_interval}min interval")
                return True
                
        except Exception as e:
            logger.error(f"Error starting agent {agent_name}: {e}")
            return False
    
    def stop_agent(self, agent_name: str) -> bool:
        """Stop scheduling an agent"""
        try:
            # Import db here to avoid circular import
            from app import db
            with self.app.app_context():
                status = AgentStatus.query.filter_by(agent_name=agent_name).first()
                if not status:
                    return False
                
                if agent_name in self.active_jobs:
                    self.scheduler.remove_job(agent_name)
                    del self.active_jobs[agent_name]
                
                status.is_active = False
                db.session.commit()
                
                logger.info(f"Stopped agent {agent_name}")
                return True
                
        except Exception as e:
            logger.error(f"Error stopping agent {agent_name}: {e}")
            return False
    
    def _run_agent(self, agent_name: str):
        """Execute an agent and store results"""
        from app import db
        with self.app.app_context():
            try:
                agent_class = get_agent_class(agent_name)
                if not agent_class:
                    logger.error(f"Agent class not found: {agent_name}")
                    return
                
                agent = agent_class()
                findings = agent.run()
                
                # Update agent status
                status = AgentStatus.query.filter_by(agent_name=agent_name).first()
                if status:
                    status.last_run = datetime.utcnow()
                    status.run_count += 1
                    status.last_error = None
                
                # Store findings
                if findings:
                    for finding_data in findings:
                        finding = Finding()
                        finding.agent_name = agent_name
                        finding.title = finding_data.get('title', 'Anomaly Detected')
                        finding.description = finding_data.get('description', '')
                        finding.severity = finding_data.get('severity', 'medium')
                        finding.confidence = finding_data.get('confidence', 0.5)
                        finding.finding_metadata = finding_data.get('metadata', {})
                        finding.symbol = finding_data.get('symbol')
                        finding.market_type = finding_data.get('market_type')
                        db.session.add(finding)
                
                db.session.commit()
                logger.info(f"Agent {agent_name} completed - {len(findings) if findings else 0} findings")
                
            except Exception as e:
                logger.error(f"Error running agent {agent_name}: {e}")
                
                # Update error status
                status = AgentStatus.query.filter_by(agent_name=agent_name).first()
                if status:
                    status.error_count += 1
                    status.last_error = str(e)
                    db.session.commit()
    
    def get_agent_status(self) -> Dict:
        """Get status of all agents"""
        from app import db
        with self.app.app_context():
            statuses = AgentStatus.query.all()
            return {status.agent_name: status.to_dict() for status in statuses}
    
    def update_agent_interval(self, agent_name: str, interval_minutes: int) -> bool:
        """Update agent scheduling interval"""
        try:
            from app import db
            with self.app.app_context():
                status = AgentStatus.query.filter_by(agent_name=agent_name).first()
                if not status:
                    return False
                
                status.schedule_interval = interval_minutes
                
                # Restart job if active
                if agent_name in self.active_jobs:
                    self.stop_agent(agent_name)
                    self.start_agent(agent_name)
                
                db.session.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error updating agent interval: {e}")
            return False
