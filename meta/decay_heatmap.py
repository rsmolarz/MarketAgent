"""
Agent Decay Heatmap by Regime

Collects and visualizes which agents decay in which market regimes.
This diagnostic explains:
- Why agents get muted
- Whether decay is regime-specific or structural
- Which agents to rotate into, not just out of
"""

from collections import defaultdict
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class DecayHeatmap:
    """
    Collects decay × regime matrix data for visualization and analysis.
    
    Pattern interpretation:
    - Red across all regimes → Agent structurally broken
    - Red only in "risk_on" → Agent is defensive
    - Green only in "volatility" → Crisis-alpha specialist
    - Diagonal stripes → Regime specialist
    - Flat green → Core allocator anchor
    """
    
    def __init__(self, window_days: int = 30, max_samples: int = 10000):
        self.window_days = window_days
        self.max_samples = max_samples
        self.data = defaultdict(lambda: defaultdict(list))
        self.timestamps = defaultdict(lambda: defaultdict(list))
    
    def ingest(self, regime: str, agent: str, decay_value: float, timestamp: datetime = None):
        """
        Record a decay value for an agent in a specific regime.
        
        Args:
            regime: Current market regime (risk_on, risk_off, volatility, etc.)
            agent: Agent name
            decay_value: Current decay multiplier (0-1)
            timestamp: Optional timestamp (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        self.data[regime][agent].append(decay_value)
        self.timestamps[regime][agent].append(timestamp)
        
        if len(self.data[regime][agent]) > self.max_samples:
            self.data[regime][agent] = self.data[regime][agent][-self.max_samples:]
            self.timestamps[regime][agent] = self.timestamps[regime][agent][-self.max_samples:]
    
    def summarize(self, recent_days: int = None) -> dict:
        """
        Compute mean decay per agent per regime.
        
        Returns:
            {regime: {agent: mean_decay}}
        """
        if recent_days is None:
            recent_days = self.window_days
        
        cutoff = datetime.utcnow() - timedelta(days=recent_days)
        summary = {}
        
        for regime, agents in self.data.items():
            summary[regime] = {}
            for agent, vals in agents.items():
                timestamps = self.timestamps[regime][agent]
                recent_vals = [
                    v for v, t in zip(vals, timestamps)
                    if t >= cutoff
                ]
                if recent_vals:
                    summary[regime][agent] = sum(recent_vals) / len(recent_vals)
        
        return summary
    
    def get_agent_regime_profile(self, agent: str) -> dict:
        """
        Get decay profile for a single agent across all regimes.
        
        Returns:
            {regime: mean_decay}
        """
        summary = self.summarize()
        return {
            regime: agents.get(agent, None)
            for regime, agents in summary.items()
            if agent in agents
        }
    
    def classify_agent(self, agent: str) -> str:
        """
        Auto-label agent based on decay patterns.
        
        Returns one of:
        - "structurally_dead": decay < 0.2 across all regimes
        - "defensive": decays in risk_on, survives in risk_off
        - "crisis_alpha": strong only in volatility/stress regimes
        - "regime_specialist": good in specific regimes only
        - "core_anchor": stable green across all regimes
        - "unknown": insufficient data
        """
        profile = self.get_agent_regime_profile(agent)
        
        if not profile:
            return "unknown"
        
        values = list(profile.values())
        mean_decay = sum(values) / len(values) if values else 0
        
        if mean_decay < 0.2:
            return "structurally_dead"
        
        if mean_decay > 0.7:
            return "core_anchor"
        
        risk_on_decay = profile.get("risk_on", profile.get("bullish", 0.5))
        risk_off_decay = profile.get("risk_off", profile.get("bearish", 0.5))
        volatility_decay = profile.get("volatility", profile.get("crisis", 0.5))
        
        if risk_on_decay < 0.3 and risk_off_decay > 0.5:
            return "defensive"
        
        if volatility_decay > 0.6 and risk_on_decay < 0.4:
            return "crisis_alpha"
        
        variance = sum((v - mean_decay) ** 2 for v in values) / len(values) if values else 0
        if variance > 0.1:
            return "regime_specialist"
        
        return "unknown"
    
    def get_heatmap_data(self) -> dict:
        """
        Get data formatted for heatmap visualization.
        
        Returns:
            {
                'regimes': [list of regime names],
                'agents': [list of agent names],
                'matrix': [[decay values]],
                'classifications': {agent: classification}
            }
        """
        summary = self.summarize()
        
        all_regimes = sorted(summary.keys())
        all_agents = sorted(set(
            agent for agents in summary.values() for agent in agents
        ))
        
        matrix = []
        for regime in all_regimes:
            row = []
            for agent in all_agents:
                row.append(summary.get(regime, {}).get(agent, None))
            matrix.append(row)
        
        classifications = {
            agent: self.classify_agent(agent)
            for agent in all_agents
        }
        
        return {
            'regimes': all_regimes,
            'agents': all_agents,
            'matrix': matrix,
            'classifications': classifications
        }
    
    def get_weak_agents_for_regime(self, regime: str, threshold: float = 0.3) -> list:
        """
        Find agents that are weak (decaying) in a specific regime.
        
        Returns:
            List of (agent_name, decay_value) tuples
        """
        summary = self.summarize()
        regime_data = summary.get(regime, {})
        
        weak = [
            (agent, decay)
            for agent, decay in regime_data.items()
            if decay < threshold
        ]
        
        return sorted(weak, key=lambda x: x[1])
    
    def get_strong_agents_for_regime(self, regime: str, threshold: float = 0.6) -> list:
        """
        Find agents that are strong in a specific regime.
        
        Returns:
            List of (agent_name, decay_value) tuples
        """
        summary = self.summarize()
        regime_data = summary.get(regime, {})
        
        strong = [
            (agent, decay)
            for agent, decay in regime_data.items()
            if decay >= threshold
        ]
        
        return sorted(strong, key=lambda x: x[1], reverse=True)


decay_heatmap = DecayHeatmap()
