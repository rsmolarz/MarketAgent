"""
Scheduler Integration for Distressed Property & Deal Agents
============================================================
Add this to your scheduler.py to register the new agents.
"""

# ==============================================================================
# AGENT DEFINITIONS (add to your AGENTS dict)
# ==============================================================================

DISTRESSED_AGENTS = {
    "DistressedPropertyAgent": {
        "module": "agents.distressed_property_agent",
        "class": "DistressedPropertyAgent",
        "callable": "analyze",
        "interval_minutes": 60,
        "enabled": True,
        "regime_sensitive": False,  # Runs in all regimes
        "sandbox_editable": True,
        "execution_sensitive": False,
        "telemetry_tag": "distressed_property",
        "description": "Identifies high-signal distressed real estate opportunities"
    },
    "DistressedDealEvaluatorAgent": {
        "module": "agents.distressed_deal_evaluator_agent",
        "class": "DistressedDealEvaluatorAgent",
        "callable": "analyze",
        "interval_minutes": 120,  # Every 2 hours - deals don't change fast
        "enabled": True,
        "regime_sensitive": True,  # More active in risk_off
        "regime_weight": {
            "risk_on": 0.5,
            "risk_off": 1.5,
            "crisis": 2.0
        },
        "sandbox_editable": True,
        "execution_sensitive": False,
        "telemetry_tag": "distressed_deals",
        "description": "Institutional-grade distressed debt/equity evaluation"
    }
}


# ==============================================================================
# SCHEDULER REGISTRATION (add this method to AgentScheduler class)
# ==============================================================================

def register_distressed_agents(self):
    """Register distressed property and deal evaluation agents."""
    from agents.distressed_property_agent import DistressedPropertyAgent
    from agents.distressed_deal_evaluator_agent import DistressedDealEvaluatorAgent
    
    # Register DistressedPropertyAgent
    property_agent = DistressedPropertyAgent()
    self.start_agent(
        agent_name="DistressedPropertyAgent",
        agent_instance=property_agent,
        interval_minutes=60,
        run_immediately=False
    )
    
    # Register DistressedDealEvaluatorAgent
    deal_agent = DistressedDealEvaluatorAgent()
    self.start_agent(
        agent_name="DistressedDealEvaluatorAgent",
        agent_instance=deal_agent,
        interval_minutes=120,
        run_immediately=True  # Run once on startup
    )
    
    logger.info("Registered distressed agents: Property (60min), DealEvaluator (120min)")


# ==============================================================================
# SIGNAL HANDLER (add to your signal processing pipeline)
# ==============================================================================

def process_distressed_signals(self, signals: list, agent_name: str):
    """
    Process signals from distressed agents.
    Stores to database and triggers alerts for high-conviction signals.
    """
    from datetime import datetime
    
    high_conviction = []
    
    for signal in signals:
        # Store all signals
        self._store_signal(
            agent=agent_name,
            signal_type=signal.get("signal_type"),
            strength=signal.get("signal_strength"),
            data=signal,
            timestamp=datetime.utcnow()
        )
        
        # Track high-conviction for alerts
        if signal.get("signal_strength", 0) >= 75:
            high_conviction.append(signal)
    
    # Trigger alerts for high-conviction signals
    if high_conviction:
        self._send_distressed_alert(high_conviction, agent_name)
    
    return len(signals), len(high_conviction)


def _send_distressed_alert(self, signals: list, agent_name: str):
    """Send alert for high-conviction distressed opportunities."""
    from tools.email_client import send_email
    
    subject = f"🏠 High-Conviction Distressed Signal: {len(signals)} opportunities"
    
    body_lines = [
        f"<h2>{agent_name} Alert</h2>",
        f"<p>Found {len(signals)} high-conviction opportunities:</p>",
        "<table border='1' cellpadding='5'>",
        "<tr><th>ID</th><th>Type</th><th>Strength</th><th>Details</th></tr>"
    ]
    
    for sig in signals[:10]:  # Top 10
        if agent_name == "DistressedPropertyAgent":
            details = f"{sig.get('address', 'N/A')}, {sig.get('city', '')}, {sig.get('state', '')}"
            details += f" | {sig.get('status', '')} | ${sig.get('price', 0):,.0f}"
        else:
            details = f"{sig.get('company_name', 'N/A')} | {sig.get('distress_level', '')}"
            details += f" | IRR: {sig.get('expected_irr', 0):.1%}"
        
        body_lines.append(
            f"<tr>"
            f"<td>{sig.get('property_id', sig.get('deal_id', 'N/A'))}</td>"
            f"<td>{sig.get('signal_type', 'N/A')}</td>"
            f"<td>{sig.get('signal_strength', 0):.0f}</td>"
            f"<td>{details}</td>"
            f"</tr>"
        )
    
    body_lines.append("</table>")
    
    send_email(
        to=self.config.get("alert_email", "alerts@yourfund.com"),
        subject=subject,
        body="\n".join(body_lines),
        html=True
    )


# ==============================================================================
# DATABASE SCHEMA (add to your schema migrations)
# ==============================================================================

DISTRESSED_SIGNALS_SCHEMA = """
CREATE TABLE IF NOT EXISTS distressed_property_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id TEXT NOT NULL,
    address TEXT,
    city TEXT,
    state TEXT,
    zip_code TEXT,
    signal_type TEXT NOT NULL,
    signal_strength REAL NOT NULL,
    price REAL,
    estimated_value REAL,
    discount_pct REAL,
    property_type TEXT,
    status TEXT,
    source TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(property_id, signal_type, DATE(created_at))
);

CREATE TABLE IF NOT EXISTS distressed_deal_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deal_id TEXT NOT NULL,
    company_name TEXT NOT NULL,
    industry TEXT,
    distress_level TEXT,
    altman_z_score REAL,
    probability_of_default REAL,
    going_concern_value REAL,
    liquidation_value REAL,
    total_debt REAL,
    fulcrum_security TEXT,
    fulcrum_trading_price REAL,
    weighted_recovery REAL,
    expected_irr REAL,
    signal_type TEXT NOT NULL,
    signal_strength REAL NOT NULL,
    risk_reward_score REAL,
    thesis TEXT,
    source TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(deal_id, DATE(created_at))
);

CREATE INDEX IF NOT EXISTS idx_property_signals_strength 
    ON distressed_property_signals(signal_strength DESC);
CREATE INDEX IF NOT EXISTS idx_property_signals_type 
    ON distressed_property_signals(signal_type);
CREATE INDEX IF NOT EXISTS idx_deal_signals_irr 
    ON distressed_deal_signals(expected_irr DESC);
CREATE INDEX IF NOT EXISTS idx_deal_signals_strength 
    ON distressed_deal_signals(signal_strength DESC);
"""


# ==============================================================================
# FULL SCHEDULER INTEGRATION EXAMPLE
# ==============================================================================

"""
To integrate into your existing scheduler.py:

1. Import the agents at top:
   from agents.distressed_property_agent import DistressedPropertyAgent
   from agents.distressed_deal_evaluator_agent import DistressedDealEvaluatorAgent

2. Add to your AGENTS dict or agent loading:
   self.agents["DistressedPropertyAgent"] = DistressedPropertyAgent()
   self.agents["DistressedDealEvaluatorAgent"] = DistressedDealEvaluatorAgent()

3. In your _load_schedule() method, add:
   self.start_agent("DistressedPropertyAgent", interval_minutes=60)
   self.start_agent("DistressedDealEvaluatorAgent", interval_minutes=120)

4. In your signal processing, route to process_distressed_signals():
   if agent_name.startswith("Distressed"):
       self.process_distressed_signals(signals, agent_name)

5. Run database migrations for the new tables.
"""
