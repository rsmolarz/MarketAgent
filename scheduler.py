import json
import threading
import time
import logging
from datetime import datetime
from typing import Dict, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from agents import get_agent_class
from models import AgentStatus, Finding
from services.agent_run_wrapper import run_with_telemetry
from services.kill_switch import is_killed
from meta_supervisor.kill_list import is_killed as meta_is_killed
from meta_supervisor.policy.kill_switch import agent_disabled as policy_agent_disabled
from notifiers.email_meta import send_meta_email
from meta.allocator import UCBAllocator
from meta.quarantine_manager import run as quarantine_run
from trading.guardrails import TradeGuardrails, GuardrailConfig, KillSwitch
from backtests.registry import is_agent_enabled as meta_agent_enabled
from meta.regime_rotation import apply_regime_rotation, load_regime_stats
from meta.llm_council import run_llm_council
from meta.uncertainty import compute_controls
from meta.decay import _decay
from meta.heatmap import _failure_heatmap

logger = logging.getLogger(__name__)

_cached_regime_state = None
_regime_weights = {}
_uncertainty_state = None
_force_started_agents = set()

class AgentScheduler:
    def __init__(self, app=None):
        self.app = app
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        self.active_jobs = {}
        self.agents = {}  # Store loaded agent instances
        self.allocator = UCBAllocator()
        self.guardrails = TradeGuardrails(
            GuardrailConfig(paper_only=True),
            KillSwitch()
        )
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize with Flask app"""
        self.app = app
        with app.app_context():
            self.load_schedule()
            self.schedule_daily_emails()
            self.schedule_discovery_agents()
            self.schedule_alpha_reconciliation()
            self.schedule_sim_model_training()
            self.schedule_meta_reports()
            self.schedule_lp_email()
            self.schedule_meta_supervisor()
            self.schedule_portfolio_allocation()
            self.schedule_telemetry_rollups()
            self.schedule_quarantine()
            self.schedule_regime_rotation()
            self.schedule_uncertainty()
            self.schedule_regime_transition_watch()
    
    def load_schedule(self):
        """Load agent schedule from JSON file and auto-start agents"""
        try:
            with open("agent_schedule.json", "r") as f:
                schedule_data = json.load(f)
                
            # Import db here to avoid circular import
            from models import db
            started_count = 0
            for agent_name, value in schedule_data.items():
                # Handle both legacy format (int) and new Meta-Agent format (dict)
                if isinstance(value, (int, float)):
                    interval_minutes = int(value)
                    enabled = True
                else:
                    interval_minutes = value.get("interval", 30)
                    enabled = value.get("enabled", True)
                
                # Ensure agent status exists in database
                status = AgentStatus.query.filter_by(agent_name=agent_name).first()
                if not status:
                    status = AgentStatus()
                    status.agent_name = agent_name
                    status.schedule_interval = interval_minutes
                    status.is_active = False
                    db.session.add(status)
                    db.session.commit()
                else:
                    # Update interval if changed
                    status.schedule_interval = interval_minutes
                    db.session.commit()
                
                # Only auto-start agents that are enabled
                if enabled:
                    self.start_agent(agent_name)
                    started_count += 1
                else:
                    logger.info(f"Agent {agent_name} disabled by Meta-Agent, not starting")
                
            logger.info(f"Loaded schedule: {started_count}/{len(schedule_data)} agents started")
                
        except FileNotFoundError:
            logger.warning("agent_schedule.json not found, using default schedule")
            self.create_default_schedule()
        except Exception as e:
            logger.error(f"Error loading schedule: {e}")
            self.create_default_schedule()
    
    def create_default_schedule(self):
        """Create default schedule for all available agents and auto-start them"""
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
        from models import db
        for agent_name, interval in default_agents.items():
            status = AgentStatus.query.filter_by(agent_name=agent_name).first()
            if not status:
                status = AgentStatus()
                status.agent_name = agent_name
                status.schedule_interval = interval
                status.is_active = False
                db.session.add(status)
                db.session.commit()
            
            # Auto-start all default agents
            self.start_agent(agent_name)
        
        logger.info(f"Created default schedule and auto-started {len(default_agents)} agents")
    
    def start_agent(self, agent_name: str, force: bool = False) -> bool:
        """Start scheduling an agent
        
        Args:
            agent_name: Name of the agent to start
            force: If True, bypass regime/drawdown restrictions
        """
        try:
            from models import db
            with self.app.app_context():
                status = AgentStatus.query.filter_by(agent_name=agent_name).first()
                if not status:
                    logger.error(f"Agent {agent_name} not found in database")
                    return False
                
                if agent_name in self.active_jobs:
                    logger.warning(f"Agent {agent_name} is already scheduled")
                    return True
                
                if force:
                    _force_started_agents.add(agent_name)
                    logger.info(f"Force-starting agent {agent_name} (bypassing restrictions)")
                
                job = self.scheduler.add_job(
                    func=lambda name=agent_name: run_with_telemetry(name, self._run_agent, name),
                    trigger=IntervalTrigger(minutes=status.schedule_interval),
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
            logger.warning(f"[CodeGuardian] Agent {agent_name} startup failed")
            from services.startup_failure_tracker import track_startup_failure
            track_startup_failure(agent_name, str(e), str(type(e).__name__))
            return False
    
    def stop_agent(self, agent_name: str) -> bool:
        """Stop scheduling an agent"""
        try:
            # Import db here to avoid circular import
            from models import db
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
        from models import db
        from alpha.emit import emit_alpha_signal
        
        is_force_started = agent_name in _force_started_agents
        SYSTEM_AGENTS = ['CodeGuardianAgent', 'HealthCheckAgent', 'MetaSupervisorAgent']
        
        if not is_force_started and agent_name not in SYSTEM_AGENTS:
            if is_killed(agent_name):
                logger.warning(f"Agent {agent_name} is disabled by kill-switch")
                return
            
            if meta_is_killed(agent_name):
                logger.warning(f"Agent {agent_name} is on meta-supervisor kill-list")
                return
            
            if policy_agent_disabled(agent_name):
                logger.warning(f"Agent {agent_name} is disabled by policy kill-switch")
                return
            
            if not meta_agent_enabled(agent_name):
                logger.warning(f"Agent {agent_name} is disabled by Meta-Agent ranking")
                return
            
            if _regime_weights:
                regime_weight = _regime_weights.get(agent_name, 1.0)
                if regime_weight < 0.01:
                    logger.info(f"Agent {agent_name} muted by regime rotation (weight={regime_weight:.3f})")
                    return
        
        if is_force_started:
            logger.info(f"Agent {agent_name} running (force-started, bypassing restrictions)")
        elif agent_name in SYSTEM_AGENTS:
            logger.info(f"System agent {agent_name} bypassing regime rotation")
        
        global _uncertainty_state
        if (_uncertainty_state or {}).get("spike"):
            logger.warning(f"Uncertainty spike active: signals are provisional ({(_uncertainty_state or {}).get('label')})")
        
        with self.app.app_context():
            try:
                agent_class = get_agent_class(agent_name)
                if not agent_class:
                    logger.error(f"Agent class not found: {agent_name}")
                    return
                
                agent = agent_class()
                findings = agent.run()
                
                if isinstance(findings, dict) and "ensemble_score_final" in findings:
                    ok, reason = self.guardrails.check({
                        "notional_usd": findings.get("notional_usd", 0),
                        "expected_edge_bps": findings.get("expected_edge_bps", 0),
                        "spread_bps": findings.get("spread_bps", 0),
                        "slippage_bps": findings.get("slippage_bps", 0),
                        "data_age_sec": findings.get("data_age_sec", 999),
                        "paper": True
                    })
                    
                    if not ok:
                        logger.warning(f"Trade blocked by guardrails: {reason}")
                        return
                    
                    emit_alpha_signal(findings, agent_name)
                
                # Update agent status
                status = AgentStatus.query.filter_by(agent_name=agent_name).first()
                if status:
                    status.last_run = datetime.utcnow()
                    status.run_count += 1
                    status.last_error = None
                
                # Store findings
                stored_findings = []
                if findings:
                    for finding_data in findings:
                        finding = Finding()
                        finding.agent_name = agent_name
                        finding.title = finding_data.get('title', 'Anomaly Detected')
                        finding.description = finding_data.get('description', '')
                        finding.severity = finding_data.get('severity', 'medium')
                        finding.confidence = finding_data.get('confidence', 0.5)
                        finding.finding_metadata = {
                            **(finding_data.get('metadata', {}) or {}),
                            "provisional": bool((_uncertainty_state or {}).get("spike", False)),
                            "uncertainty_label": (_uncertainty_state or {}).get("label"),
                            "uncertainty_score": (_uncertainty_state or {}).get("score"),
                        }
                        finding.symbol = finding_data.get('symbol')
                        finding.market_type = finding_data.get('market_type')
                        db.session.add(finding)
                        db.session.flush()
                        stored_findings.append(finding)
                        
                        if finding.severity == "critical" and not finding.auto_analyzed:
                            try:
                                from services.auto_triage import auto_analyze_and_alert
                                
                                result = auto_analyze_and_alert(finding.id, force=False)
                                
                                if result.get("ok"):
                                    logger.info(f"Critical finding {finding.id}: triple-confirmation analysis complete "
                                               f"(alerted={result.get('alerted', False)})")
                                else:
                                    logger.warning(f"Critical finding {finding.id}: analysis skipped - {result.get('reason')}")
                            except Exception as analysis_err:
                                logger.error(f"Auto-analysis failed for finding {finding.id}: {analysis_err}")
                
                db.session.commit()
                
                self._run_council_on_findings(stored_findings)
                
                self._auto_create_deals(stored_findings)
                logger.info(f"Agent {agent_name} completed - {len(findings) if findings else 0} findings")
                
                uncertainty = (_uncertainty_state or {}).get("score", 0.0)
                _decay.update(agent_name, reward=len(findings or []), uncertainty=uncertainty)
                
                regime = (_cached_regime_state or {}).get("active_regime", "unknown")
                _failure_heatmap.update(agent_name, regime, len(findings or []))
                
            except Exception as e:
                logger.error(f"Error running agent {agent_name}: {e}")
                db.session.rollback()
                
                try:
                    status = AgentStatus.query.filter_by(agent_name=agent_name).first()
                    if status:
                        status.error_count += 1
                        status.last_error = str(e)[:500]
                        db.session.commit()
                except Exception:
                    db.session.rollback()
                
                _decay.update(agent_name, reward=-1, uncertainty=(_uncertainty_state or {}).get("score", 0.0))
                
                regime = (_cached_regime_state or {}).get("active_regime", "unknown")
                _failure_heatmap.update(agent_name, regime, -1)
    
    def get_agent_status(self) -> Dict:
        """Get status of all agents"""
        from models import db
        with self.app.app_context():
            statuses = AgentStatus.query.all()
            return {status.agent_name: status.to_dict() for status in statuses}
    
    def update_agent_interval(self, agent_name: str, interval_minutes: int) -> bool:
        """Update agent scheduling interval"""
        try:
            from models import db
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
    
    def run_agent_immediately(self, agent_name: str) -> bool:
        """Run an agent immediately (manually triggered)"""
        try:
            # Load agent if not already loaded
            if agent_name not in self.agents:
                if not self._load_agent(agent_name):
                    logger.error(f"Failed to load agent {agent_name}")
                    return False
            
            # Run the agent
            self._run_agent(agent_name)
            logger.info(f"Manual execution of agent {agent_name} completed")
            return True
            
        except Exception as e:
            logger.error(f"Error running agent {agent_name} manually: {e}")
            return False
    
    def _run_council_on_findings(self, findings):
        """Run LLM trade council on new findings to populate ta_council/fund_council/real_estate_council."""
        import os
        if not findings:
            return
        
        try:
            from openai import OpenAI
            
            api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY")
            base_url = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
            
            if not api_key:
                logger.debug("No OpenAI API key configured, skipping council analysis")
                return
            
            client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
            
            for finding in findings:
                try:
                    if finding.ta_council is not None:
                        continue
                    
                    is_re = finding.market_type in ('real_estate', 'private_equity', 'private_company')
                    is_re = is_re or 'distress' in (finding.agent_name or '').lower()
                    is_re = is_re or 'property' in (finding.agent_name or '').lower()
                    is_re = is_re or 'zillow' in (finding.agent_name or '').lower()
                    
                    prompt = (
                        f"Analyze this market finding. "
                        f"Agent: {finding.agent_name}, Symbol: {finding.symbol}, "
                        f"Severity: {finding.severity}, Confidence: {finding.confidence}\n"
                        f"Title: {finding.title}\n"
                        f"Description: {(finding.description or '')[:400]}\n\n"
                        f"For each council, respond ACT (trade now), WATCH (monitor), or HOLD (no action):\n"
                        f"ta_council=ACT|WATCH|HOLD\n"
                        f"fund_council=ACT|WATCH|HOLD\n"
                        f"real_estate_council=ACT|WATCH|HOLD|N/A"
                    )
                    
                    response = client.chat.completions.create(
                        model='gpt-4o-mini',
                        messages=[{'role': 'user', 'content': prompt}],
                        max_tokens=80,
                        temperature=0.2
                    )
                    
                    text = response.choices[0].message.content or ''
                    
                    for line in text.strip().split('\n'):
                        if '=' in line:
                            key, val = line.split('=', 1)
                            key = key.strip().lower()
                            val = val.strip().lower()
                            if val in ['act', 'watch', 'hold']:
                                if 'ta' in key:
                                    finding.ta_council = val
                                elif 'fund' in key:
                                    finding.fund_council = val
                                elif 'real' in key:
                                    finding.real_estate_council = val
                    
                    if is_re and finding.real_estate_council is None:
                        finding.real_estate_council = finding.ta_council or 'watch'
                    
                except Exception as e:
                    logger.debug(f"Council analysis failed for finding {finding.id}: {e}")
                    continue
            
            from models import db
            db.session.commit()
            council_count = sum(1 for f in findings if f.ta_council is not None)
            if council_count:
                logger.info(f"Council analysis completed for {council_count}/{len(findings)} findings")
            
        except Exception as e:
            logger.error(f"Council runner error: {e}")

    def _auto_create_deals(self, findings):
        """Auto-create distressed deals from real estate/PE findings."""
        if not findings:
            return
        
        try:
            from models import db, DistressedDeal
            
            deal_agent_types = {
                'distressedpropertyagent', 'zillowdistressagent',
                'distresseddealevaluatoragent', 'industrialdistressscanneragent',
                'privateequitydistressedassetfinder', 'privatecompanydistressagent',
                'bigshortdealadapter', 'distressedmacrogateagent'
            }
            deal_market_types = {'real_estate', 'private_equity', 'private_company'}
            
            created = 0
            for finding in findings:
                try:
                    agent_lower = (finding.agent_name or '').lower()
                    is_deal_agent = agent_lower in deal_agent_types
                    is_deal_market = (finding.market_type or '') in deal_market_types
                    
                    if not (is_deal_agent or is_deal_market):
                        continue
                    
                    existing = DistressedDeal.query.filter_by(finding_id=finding.id).first()
                    if existing:
                        continue
                    
                    metadata = finding.finding_metadata or {}
                    
                    address = (
                        metadata.get('address') or 
                        metadata.get('property_address') or 
                        metadata.get('company_name') or
                        metadata.get('name') or
                        finding.symbol or 
                        f"{finding.agent_name} Finding #{finding.id}"
                    )
                    
                    deal = DistressedDeal(
                        property_address=address[:255],
                        city=metadata.get('city') or metadata.get('metro'),
                        state=metadata.get('state'),
                        zip_code=metadata.get('zip_code'),
                        property_type=metadata.get('property_type') or metadata.get('sector') or finding.market_type,
                        distress_type=metadata.get('distress_type') or metadata.get('status') or 'agent_detected',
                        asking_price=metadata.get('price') or metadata.get('asking_price') or metadata.get('market_value'),
                        estimated_value=metadata.get('estimated_value') or metadata.get('zestimate') or metadata.get('recovery_value'),
                        stage='screened',
                        finding_id=finding.id,
                        source_agent=finding.agent_name,
                        deal_metadata={
                            'finding_title': finding.title,
                            'finding_severity': finding.severity,
                            'finding_confidence': finding.confidence,
                            'auto_created': True,
                            **{k: v for k, v in metadata.items() if isinstance(v, (str, int, float, bool, type(None)))}
                        }
                    )
                    
                    db.session.add(deal)
                    created += 1
                    
                except Exception as e:
                    logger.debug(f"Auto-deal creation failed for finding {finding.id}: {e}")
                    continue
            
            if created:
                db.session.commit()
                logger.info(f"Auto-created {created} deals from findings")
        
        except Exception as e:
            logger.error(f"Auto-deal creation error: {e}")

    def _load_agent(self, agent_name: str) -> bool:
        """Load an agent class and instantiate it"""
        try:
            agent_class = get_agent_class(agent_name)
            if agent_class:
                self.agents[agent_name] = agent_class()
                logger.info(f"Loaded agent: {agent_name}")
                return True
            else:
                logger.error(f"Agent class not found: {agent_name}")
                return False
        except Exception as e:
            logger.error(f"Error loading agent {agent_name}: {e}")
            return False
    
    def schedule_portfolio_allocation(self):
        """Schedule periodic portfolio allocation rebalancing"""
        try:
            self.scheduler.add_job(
                func=self._rebalance_agent_allocation,
                trigger=CronTrigger(minute="*/15"),
                id="agent_allocation",
                replace_existing=True
            )
            logger.info("Scheduled portfolio allocation every 15 minutes")
        except Exception as e:
            logger.error(f"Error scheduling portfolio allocation: {e}")
    
    def _rebalance_agent_allocation(self):
        """Rebalance agent scheduling based on reward performance"""
        from models import db, UncertaintyEvent
        from telemetry.uncertainty_events import load_recent_uncertainty
        from trading.drawdown_governor import governor
        from services.drawdown_governor import drawdown_governor as new_dd_governor
        from services.uncertainty_state import current_uncertainty_multiplier
        from meta.capital_optimizer import capital_allocate
        global _uncertainty_state
        
        with self.app.app_context():
            try:
                latest_ue = (
                    UncertaintyEvent.query
                    .order_by(UncertaintyEvent.timestamp.desc())
                    .first()
                )
                if latest_ue and latest_ue.spike and self.allocator.exploration > 0.1:
                    self.allocator.exploration = max(0.1, self.allocator.exploration * latest_ue.decay_multiplier)
                    logger.info(f"Allocator exploration reduced to {self.allocator.exploration:.2f} due to uncertainty spike")
                
                self.allocator.ingest_events()
                
                agent_names = list(self.active_jobs.keys())
                if not agent_names:
                    return
                
                cadence_mult = float((_uncertainty_state or {}).get("cadence_multiplier", 1.0))
                decay_mult = float((_uncertainty_state or {}).get("decay_multiplier", 1.0))
                
                dd_gov = governor({"total_budget_runs": 30}, dd_limit=-3.0)
                if dd_gov.get("drawdown_breached"):
                    cadence_mult *= dd_gov.get("cadence_multiplier", 0.5)
                    decay_mult *= dd_gov.get("budget_multiplier", 0.5)
                    logger.warning(f"Drawdown breached: {dd_gov.get('reason')}")
                
                new_gov = new_dd_governor(dd_limit=-3.0)
                if new_gov.get("halt"):
                    logger.warning(f"Portfolio HALT (drawdown={new_gov['dd']:.2f}). Blocking alpha emission.")
                    return
                
                agent_uncertainty = load_recent_uncertainty()
                
                from meta.uncertainty import all_agent_uncertainties
                persisted_uncertainties = all_agent_uncertainties(lookback_days=14)
                for agent, unc in persisted_uncertainties.items():
                    if agent not in agent_names:
                        continue
                    if agent in agent_uncertainty:
                        agent_uncertainty[agent] = max(agent_uncertainty[agent], unc)
                    else:
                        agent_uncertainty[agent] = unc
                
                agent_uncertainty = {k: v for k, v in agent_uncertainty.items() if k in agent_names}
                
                base_budget = 30
                effective_budget = max(10, int(base_budget * decay_mult))
                
                quotas, scores = self.allocator.allocate(
                    agents=agent_names,
                    min_runs={"MacroWatcherAgent": 1},
                    max_runs={"ArbitrageFinderAgent": 12},
                    total_budget_runs=effective_budget,
                    uncertainty_decay=decay_mult,
                    agent_uncertainty=agent_uncertainty
                )
                
                base_weights = {}
                for a in agent_names:
                    cfg = self.agent_schedule.get(a, {})
                    if isinstance(cfg, dict):
                        base_weights[a] = cfg.get("weight", 1.0) if cfg.get("enabled", True) else 0.0
                    else:
                        base_weights[a] = 1.0
                
                effective_regime_weights = _regime_weights if _regime_weights else base_weights
                
                unc_mult = current_uncertainty_multiplier()
                try:
                    notional_map = capital_allocate(
                        base_weights=base_weights,
                        regime_weights=effective_regime_weights,
                        allocator_scores=scores,
                        uncertainty_mult=unc_mult,
                        drawdown_mult=new_gov.get("risk_multiplier", 1.0),
                        total_notional=100000.0
                    )
                    
                    top_allocs = sorted(notional_map.items(), key=lambda x: x[1], reverse=True)[:5]
                    logger.info(f"Capital allocation (top): {top_allocs}")
                except Exception as alloc_err:
                    logger.warning(f"Capital allocation failed: {alloc_err}, using quotas only")
                
                from meta.uncertainty_policy import cadence_multiplier
                from meta.fail_first_penalty import apply_fail_first_penalty, compute_fail_first_multiplier
                
                uncertainty_level = float((_uncertainty_state or {}).get("score", 0.0))
                
                if uncertainty_level >= 0.5:
                    penalized_quotas = {}
                    for agent, runs in quotas.items():
                        ff_mult = compute_fail_first_multiplier(agent, uncertainty_level)
                        penalized_quotas[agent] = max(1, int(runs * ff_mult))
                    quotas = penalized_quotas
                    logger.info(f"Applied fail-first penalties at uncertainty={uncertainty_level:.2f}")
                
                for agent_name, runs in quotas.items():
                    status = AgentStatus.query.filter_by(agent_name=agent_name).first()
                    if not status:
                        continue
                    
                    base_interval = max(1, int(60 / max(runs, 1)))
                    agent_u = agent_uncertainty.get(agent_name, 0.0)
                    mult = cadence_multiplier(agent_u)
                    effective_unc = max(0.1, unc_mult)
                    new_interval = max(1, int((base_interval * mult) / effective_unc))
                    
                    if status.schedule_interval != new_interval:
                        self.update_agent_interval(agent_name, new_interval)
                
                logger.info(f"Rebalanced agent allocation (budget={effective_budget}, uncertainties={len(agent_uncertainty)}): {scores}")
            except Exception as e:
                logger.error(f"Error rebalancing agent allocation: {e}")
    
    def schedule_telemetry_rollups(self):
        """Schedule periodic telemetry rollups"""
        try:
            self.scheduler.add_job(
                func=self._telemetry_rollups,
                trigger=IntervalTrigger(minutes=5),
                id="telemetry_rollups",
                replace_existing=True
            )
            logger.info("Scheduled telemetry rollups every 5 minutes")
        except Exception as e:
            logger.error(f"Error scheduling telemetry rollups: {e}")
    
    def _telemetry_rollups(self):
        """Run telemetry rollups"""
        with self.app.app_context():
            try:
                from telemetry.rollup import rollup as telemetry_rollup
                telemetry_rollup()
                logger.debug("Telemetry rollup completed")
            except Exception as e:
                logger.error(f"Telemetry rollup error: {e}")
    
    def schedule_quarantine(self):
        """Schedule periodic quarantine checks"""
        try:
            self.scheduler.add_job(
                func=self._run_quarantine_checks,
                trigger=IntervalTrigger(minutes=5),
                id="quarantine_checks",
                replace_existing=True
            )
            logger.info("Scheduled quarantine checks every 5 minutes")
        except Exception as e:
            logger.error(f"Error scheduling quarantine checks: {e}")
    
    def _run_quarantine_checks(self):
        """Run quarantine checks based on drawdown"""
        with self.app.app_context():
            try:
                res = quarantine_run(window=500, last_n=5000, dd_limit=-10.0)
                logger.info(f"Quarantine check: quarantined={res.get('quarantined')} cleared={res.get('cleared')}")
            except Exception as e:
                logger.error(f"Quarantine check error: {e}")
    
    def schedule_uncertainty(self):
        """Schedule uncertainty state updates every 5 minutes"""
        try:
            self.scheduler.add_job(
                func=self._update_uncertainty_state,
                trigger=IntervalTrigger(minutes=5),
                id="uncertainty_state",
                replace_existing=True
            )
            self._update_uncertainty_state()
            logger.info("Scheduled uncertainty state updates every 5 minutes")
        except Exception as e:
            logger.error(f"Error scheduling uncertainty updates: {e}")

    def _update_uncertainty_state(self):
        """Update global uncertainty state using LLM council + recent findings"""
        global _uncertainty_state, _cached_regime_state

        with self.app.app_context():
            try:
                from models import db, UncertaintyEvent

                recent = (
                    Finding.query
                    .order_by(Finding.timestamp.desc())
                    .limit(25)
                    .all()
                )
                top_findings = [{
                    "agent": f.agent_name,
                    "title": f.title,
                    "severity": f.severity,
                    "symbol": f.symbol,
                    "market_type": f.market_type
                } for f in recent]

                payload = {
                    "regime_state": _cached_regime_state,
                    "top_findings": top_findings,
                }

                council = run_llm_council(payload)
                controls = compute_controls(council, _uncertainty_state)

                evt = UncertaintyEvent()
                evt.label = controls["label"]
                evt.score = controls["score"]
                evt.spike = controls["spike"]
                evt.disagreement = controls.get("disagreement", 0.0)
                evt.votes = controls.get("votes", [])
                evt.active_regime = (_cached_regime_state or {}).get("active_regime") if isinstance(_cached_regime_state, dict) else None
                evt.regime_confidence = (_cached_regime_state or {}).get("confidence") if isinstance(_cached_regime_state, dict) else None
                evt.cadence_multiplier = controls["cadence_multiplier"]
                evt.decay_multiplier = controls["decay_multiplier"]

                db.session.add(evt)
                db.session.commit()

                _uncertainty_state = controls

                logger.info(
                    f"Uncertainty updated: label={evt.label} score={evt.score:.2f} "
                    f"spike={evt.spike} disagree={evt.disagreement:.2f} "
                    f"cadence_x{evt.cadence_multiplier:.2f} decay_x{evt.decay_multiplier:.2f}"
                )

            except Exception as e:
                logger.error(f"Uncertainty update error: {e}")

    def schedule_regime_transition_watch(self):
        """Schedule regime transition early-warning detection every 5 minutes"""
        try:
            self.scheduler.add_job(
                func=self._run_regime_transition_watch,
                trigger=IntervalTrigger(minutes=5),
                id="regime_transition_watch",
                replace_existing=True
            )
            logger.info("Scheduled regime transition watch every 5 minutes")
        except Exception as e:
            logger.error(f"Error scheduling regime transition watch: {e}")
    
    def _run_regime_transition_watch(self):
        """Check for early warning signs of regime transition"""
        with self.app.app_context():
            try:
                from regime.transition_detector import detect_transition
                
                res = detect_transition(window_minutes=60, spike_threshold=0.5)
                
                if res.get("transition"):
                    logger.warning(f"REGIME TRANSITION EARLY WARNING: {res}")
                    
                    if res.get("severity") == "high":
                        try:
                            from notifiers.email_meta import send_meta_email
                            subject = f"ALERT: Regime Transition Warning ({res.get('severity', 'unknown').upper()})"
                            text = (
                                f"Regime transition early warning detected.\n\n"
                                f"Severity: {res.get('severity')}\n"
                                f"Reason: {res.get('reason')}\n"
                                f"Delta: {res.get('delta', 0):.2f}\n"
                                f"Current level: {res.get('current', 0):.2f}\n"
                                f"Trend: {res.get('trend', 0):.2f}\n"
                                f"Spike count: {res.get('spike_count', 0)}\n"
                            )
                            send_meta_email(subject, text, f"<pre>{text}</pre>")
                            logger.info("Regime transition alert email sent")
                        except Exception as email_err:
                            logger.error(f"Failed to send transition alert email: {email_err}")
                else:
                    logger.debug(f"Regime stable: {res.get('reason', 'ok')}")
                    
            except Exception as e:
                logger.error(f"Regime transition watch error: {e}")
    
    def schedule_daily_emails(self):
        """Schedule daily email summary to whitelisted users"""
        try:
            self.scheduler.add_job(
                func=self._send_daily_emails,
                trigger=CronTrigger(hour=7, minute=0),
                id='daily_email_summary',
                replace_existing=True
            )
            self.scheduler.add_job(
                func=self._send_weekly_ic_memo,
                trigger=CronTrigger(day_of_week="sun", hour=12, minute=0),
                id="weekly_ic_memo",
                replace_existing=True
            )
            self.scheduler.add_job(
                func=self._send_compressed_ic_memo,
                trigger=CronTrigger(hour=12, minute=5),
                id="compressed_ic_memo",
                replace_existing=True
            )
            logger.info("Scheduled daily email summary for 7:00 AM UTC")
            logger.info("Scheduled compressed IC memo for 12:05 PM UTC")
        except Exception as e:
            logger.error(f"Error scheduling daily emails: {e}")
    
    def _send_daily_emails(self):
        """Send daily email summary"""
        with self.app.app_context():
            try:
                from services.daily_email_service import DailyEmailService
                service = DailyEmailService()
                service.send_daily_summary()
                logger.info("Daily email summary sent")
            except Exception as e:
                logger.error(f"Error sending daily emails: {e}")
    
    def send_daily_email_now(self) -> bool:
        """Manually trigger daily email send"""
        try:
            self._send_daily_emails()
            return True
        except Exception as e:
            logger.error(f"Error sending daily email manually: {e}")
            return False
    
    def _send_weekly_ic_memo(self):
        """Generate and send weekly IC memo"""
        with self.app.app_context():
            try:
                from meta_supervisor.ic_memo import main as build_memo
                from meta_supervisor.email_ic_memo import send_ic_memo
                build_memo()
                send_ic_memo()
                logger.info("Weekly IC memo sent")
            except Exception as e:
                logger.error(f"Weekly IC memo error: {e}")
    
    def _send_compressed_ic_memo(self):
        """Send compressed IC memo based on signal compression"""
        with self.app.app_context():
            try:
                from services.ic_memo_email import send_ic_memo_compressed
                result = send_ic_memo_compressed(hours=24)
                if result.get("sent"):
                    logger.info(f"Compressed IC memo sent: {result.get('theses', 0)} theses to {result.get('recipients', 0)} recipients")
                elif result.get("skipped"):
                    logger.debug(f"Compressed IC memo skipped: {result.get('reason')}")
                else:
                    logger.warning(f"Compressed IC memo: {result}")
            except Exception as e:
                logger.error(f"Compressed IC memo error: {e}")
    
    def send_ic_memo_now(self) -> bool:
        """Manually trigger IC memo generation and send"""
        try:
            self._send_weekly_ic_memo()
            return True
        except Exception as e:
            logger.error(f"Error sending IC memo: {e}")
            return False
    
    def _send_exec_summary(self):
        """Send Meta-Agent executive summary email"""
        with self.app.app_context():
            try:
                from meta_supervisor.summary import build_exec_summary
                subject, text, html = build_exec_summary()
                send_meta_email(subject, text, html)
                logger.info("Meta-Agent executive email sent")
            except Exception as e:
                logger.error(f"Meta-Agent email error: {e}")
    
    def send_exec_summary_now(self) -> bool:
        """Manually trigger Meta-Agent executive summary email"""
        try:
            self._send_exec_summary()
            return True
        except Exception as e:
            logger.error(f"Error sending exec summary: {e}")
            return False
    
    def schedule_discovery_agents(self):
        """Schedule discovery agents to run daily"""
        try:
            self.scheduler.add_job(
                func=self._run_discovery_agents,
                trigger=CronTrigger(hour=8, minute=25),
                id="discovery_agents_daily",
                replace_existing=True
            )
            logger.info("Scheduled discovery agents for 8:25 AM UTC")
        except Exception as e:
            logger.error(f"Error scheduling discovery agents: {e}")

    def _run_discovery_agents(self):
        """Run all discovery agents"""
        with self.app.app_context():
            try:
                from discovery_agents.literature_scanner import run as lit_run
                from discovery_agents.failure_forensics import run as forensics_run
                from discovery_agents.regime_generator import run as regime_run

                lit_run()
                forensics_run()
                regime_run()

                logger.info("Discovery agents completed")
            except Exception as e:
                logger.error(f"Discovery agents error: {e}")
    
    def run_discovery_agents_now(self) -> bool:
        """Manually trigger discovery agents"""
        try:
            self._run_discovery_agents()
            return True
        except Exception as e:
            logger.error(f"Error running discovery agents: {e}")
            return False
    
    def schedule_alpha_reconciliation(self):
        """Schedule alpha signal reconciliation every 30 minutes"""
        try:
            self.scheduler.add_job(
                func=self._run_alpha_reconciliation,
                trigger=CronTrigger(minute="*/30"),
                id="alpha_reconcile",
                replace_existing=True
            )
            logger.info("Scheduled alpha reconciliation every 30 minutes")
        except Exception as e:
            logger.error(f"Error scheduling alpha reconciliation: {e}")

    def _run_alpha_reconciliation(self):
        """Run alpha signal reconciliation"""
        with self.app.app_context():
            try:
                from alpha.reconcile import main as reconcile_main
                count = reconcile_main()
                logger.info(f"Alpha reconciliation completed: {count} signals")
            except Exception as e:
                logger.error(f"Alpha reconciliation error: {e}")
    
    def run_alpha_reconciliation_now(self) -> bool:
        """Manually trigger alpha reconciliation"""
        try:
            self._run_alpha_reconciliation()
            return True
        except Exception as e:
            logger.error(f"Error running alpha reconciliation: {e}")
            return False

    def schedule_sim_model_training(self):
        """Schedule sim model training daily at 2 AM UTC"""
        try:
            self.scheduler.add_job(
                func=self._run_sim_model_training,
                trigger=CronTrigger(hour=2, minute=0),
                id="sim_model_train",
                replace_existing=True
            )
            logger.info("Scheduled sim model training daily at 02:00 UTC")
        except Exception as e:
            logger.error(f"Error scheduling sim model training: {e}")

    def _run_sim_model_training(self):
        """Train sim model for each horizon"""
        with self.app.app_context():
            try:
                from alpha.sim_model import train
                for h in [1, 4, 24]:
                    result = train(horizon_hours=h)
                    if result.get("ok"):
                        logger.info(f"Sim model trained h={h}: n={result.get('n')}, rmse={result.get('rmse_bps')}")
                    else:
                        logger.warning(f"Sim model training h={h}: {result.get('reason')}")
            except Exception as e:
                logger.error(f"Sim model training error: {e}")

    def run_sim_model_training_now(self) -> bool:
        """Manually trigger sim model training"""
        try:
            self._run_sim_model_training()
            return True
        except Exception as e:
            logger.error(f"Error running sim model training: {e}")
            return False

    def schedule_meta_reports(self):
        """Schedule meta report generation every 30 minutes and failure forensics daily"""
        try:
            self.scheduler.add_job(
                func=self._build_meta_report,
                trigger=IntervalTrigger(minutes=30),
                id="meta_report_build",
                replace_existing=True
            )
            self.scheduler.add_job(
                func=self._run_failure_forensics,
                trigger=CronTrigger(hour=8, minute=30),
                id="failure_forensics_daily",
                replace_existing=True
            )
            logger.info("Scheduled meta reports every 30 minutes, failure forensics at 8:30 AM")
        except Exception as e:
            logger.error(f"Error scheduling meta reports: {e}")

    def _build_meta_report(self):
        """Build meta supervisor report"""
        with self.app.app_context():
            try:
                from meta_supervisor.build_meta_report import main as build_main
                build_main()
                logger.info("Meta report generated")
            except Exception as e:
                logger.error(f"Meta report error: {e}")

    def _run_failure_forensics(self):
        """Run failure forensics analysis"""
        with self.app.app_context():
            try:
                from discovery_agents.failure_forensics import run as ff_run
                ff_run()
                logger.info("Failure forensics completed")
            except Exception as e:
                logger.error(f"Failure forensics error: {e}")

    def schedule_lp_email(self):
        """Schedule LP performance email at 7:10 AM UTC"""
        try:
            self.scheduler.add_job(
                func=self._send_lp_email,
                trigger=CronTrigger(hour=7, minute=10),
                id="lp_email_daily",
                replace_existing=True
            )
            logger.info("Scheduled LP email for 7:10 AM UTC")
        except Exception as e:
            logger.error(f"Error scheduling LP email: {e}")

    def _send_lp_email(self):
        """Send LP performance email"""
        with self.app.app_context():
            try:
                from services.lp_email_service import send_lp_email
                send_lp_email()
                logger.info("LP email sent")
            except Exception as e:
                logger.error(f"LP email error: {e}")

    def run_meta_report_now(self) -> bool:
        """Manually trigger meta report generation"""
        try:
            self._build_meta_report()
            return True
        except Exception as e:
            logger.error(f"Error running meta report: {e}")
            return False

    def run_lp_email_now(self) -> bool:
        """Manually trigger LP email"""
        try:
            self._send_lp_email()
            return True
        except Exception as e:
            logger.error(f"Error sending LP email: {e}")
            return False

    def schedule_meta_supervisor(self):
        """Schedule meta supervisor to run every 6 hours"""
        try:
            self.scheduler.add_job(
                func=self._run_meta_supervisor,
                trigger=CronTrigger(hour="*/6"),
                id="meta_supervisor",
                replace_existing=True
            )
            logger.info("Scheduled meta supervisor every 6 hours")
        except Exception as e:
            logger.error(f"Error scheduling meta supervisor: {e}")

    def _run_meta_supervisor(self):
        """Run meta supervisor evaluation"""
        with self.app.app_context():
            try:
                from meta_supervisor.supervisor import run_meta_supervisor
                result = run_meta_supervisor()
                logger.info(f"Meta supervisor completed: {result.get('run_id', 'unknown')}")
            except Exception as e:
                logger.error(f"Meta supervisor error: {e}")

    def run_meta_supervisor_now(self) -> bool:
        """Manually trigger meta supervisor"""
        try:
            self._run_meta_supervisor()
            return True
        except Exception as e:
            logger.error(f"Error running meta supervisor: {e}")
            return False

    def schedule_regime_rotation(self):
        """Schedule regime rotation update every 15 minutes"""
        try:
            self.scheduler.add_job(
                func=self._update_regime_weights,
                trigger=IntervalTrigger(minutes=15),
                id="regime_rotation",
                replace_existing=True
            )
            self._update_regime_weights()
            logger.info("Scheduled regime rotation every 15 minutes")
        except Exception as e:
            logger.error(f"Error scheduling regime rotation: {e}")

    def _update_regime_weights(self):
        """Update agent weights based on current market regime"""
        global _cached_regime_state, _regime_weights
        
        with self.app.app_context():
            try:
                from regime import extract_features, score_regimes, regime_confidence
                from regime.confidence import get_cached_regime, cache_regime
                from data_sources.price_loader import load_spy
                import yfinance as yf
                
                spy = load_spy(start="2020-01-01", use_cache=True)
                
                try:
                    vix = yf.download("^VIX", period="3mo", progress=False)
                except Exception:
                    vix = spy.copy()
                    vix["Close"] = 20.0
                
                try:
                    tnx = yf.download("^TNX", period="3mo", progress=False)
                except Exception:
                    tnx = spy.copy()
                    tnx["Close"] = 4.0
                
                try:
                    gld = yf.download("GLD", period="3mo", progress=False)
                except Exception:
                    gld = None
                
                if len(spy) < 20 or len(vix) < 20 or len(tnx) < 20:
                    logger.warning("Insufficient market data for regime detection")
                    return
                
                features = extract_features(spy, vix, tnx, gld)
                scores = score_regimes(features)
                
                state = regime_confidence(
                    features,
                    scores,
                    prev_regime=get_cached_regime()
                )
                
                cache_regime(state["active_regime"])
                _cached_regime_state = state
                
                with open("agent_schedule.json", "r") as f:
                    schedule = json.load(f)
                
                base_weights = {}
                for agent, cfg in schedule.items():
                    if isinstance(cfg, dict):
                        base_weights[agent] = cfg.get("weight", 1.0) if cfg.get("enabled", True) else 0.0
                    else:
                        base_weights[agent] = 1.0
                
                _regime_weights = apply_regime_rotation(
                    base_weights,
                    state["active_regime"],
                    state["confidence"]
                )
                
                try:
                    from meta.substitution import apply_substitution
                    from telemetry.uncertainty_events import load_recent_uncertainty
                    
                    uncertainty = load_recent_uncertainty()
                    for agent in list(_regime_weights.keys()):
                        _regime_weights = apply_substitution(
                            agent,
                            uncertainty.get(agent, 0.0),
                            _regime_weights
                        )
                except Exception as sub_err:
                    logger.debug(f"Substitution skipped: {sub_err}")
                
                try:
                    from meta.decay_heatmap import decay_heatmap
                    from meta.decay import _decay
                    
                    for agent in _regime_weights.keys():
                        agent_decay = _decay.get(agent)
                        decay_heatmap.ingest(
                            state["active_regime"],
                            agent,
                            agent_decay
                        )
                except Exception as hm_err:
                    logger.debug(f"Heatmap ingestion skipped: {hm_err}")
                
                try:
                    from meta.decay_heatmap import decay_heatmap
                    from meta.substitution_map import substitution_map
                    
                    heatmap_summary = decay_heatmap.summarize()
                    substitution_map.build(heatmap_summary)
                except Exception as sm_err:
                    logger.debug(f"Substitution map build skipped: {sm_err}")
                
                try:
                    from meta.agent_substitution import apply_council_substitution
                    from models import db as models_db
                    
                    subs = apply_council_substitution(state["active_regime"])
                    if subs:
                        models_db.session.commit()
                        logger.info(f"Council substitutions applied: {subs}")
                except Exception as cs_err:
                    logger.debug(f"Council substitution skipped: {cs_err}")
                
                active_count = sum(1 for w in _regime_weights.values() if w >= 0.01)
                logger.info(
                    f"Regime rotation updated: {state['active_regime']} "
                    f"(conf={state['confidence']:.2f}), {active_count} agents active"
                )
                
            except Exception as e:
                logger.error(f"Regime rotation error: {e}")
