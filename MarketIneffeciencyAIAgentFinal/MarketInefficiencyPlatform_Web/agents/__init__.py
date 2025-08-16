from __future__ import annotations
from typing import List, Type

class BaseAgent:
    name: str
    def plan(self) -> str: ...
    def act(self, context: dict | None = None) -> dict: ...
    def reflect(self, result: dict | None = None) -> str: ...
    def run(self, mode: str = "realtime") -> None:
        # Minimal no-op loop for demo
        print(f"[agent:{self.__class__.__name__}] running in {mode} (paper)")

class AgentRegistry:
    _registry: List[BaseAgent] = []

    @classmethod
    def register(cls, agent: BaseAgent) -> None:
        cls._registry.append(agent)

    @classmethod
    def get_agents(cls) -> List[BaseAgent]:
        return cls._registry

    @classmethod
    def load_and_run_agents(cls, agents_to_run: List[str], mode: str) -> None:
        print(f"Loading and running agents: {agents_to_run} in {mode} mode")
        if agents_to_run == ["all"] or "all" in agents_to_run:
            selected = cls.get_agents()
        else:
            selected = [a for a in cls.get_agents() if a.__class__.__name__ in agents_to_run]
        for a in selected:
            a.run(mode)

# Example lightweight agents (stubs)
class SpreadScannerAgent(BaseAgent):
    pass
class MomentumVolumeAgent(BaseAgent):
    pass
class PortfolioRiskAgent(BaseAgent):
    pass

# Auto-register examples for demo
AgentRegistry.register(SpreadScannerAgent())
AgentRegistry.register(MomentumVolumeAgent())
AgentRegistry.register(PortfolioRiskAgent())

from . import arbitrage_finder, macro_watcher

from . import ml_macro_detector

from . import commodities_watcher

from . import forex_anomaly
from . import equity_momentum
from . import retail_sentiment
from . import bond_stress
from . import supply_chain_disruption
from . import options_skew
from . import insider_trading_alert
from . import patent_surge
from . import alt_data_signal
from . import geopolitical_risk
from . import energy_disruption
from . import short_interest_spike
from . import whale_wallet_watcher
from . import etf_flow_shift
from . import regulatory_alert
from . import correlation_break
from . import sentiment_divergence
from . import crypto_funding_rate
from . import satellite_data