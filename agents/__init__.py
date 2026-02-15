from agents.earnings_surprise_drift_agent import EarningsSurpriseDriftAgent
from agents.intraday_volatility_spike_agent import IntradayVolatilitySpikeAgent
from agents.earnings_whisper_surprise_agent import EarningsWhisperSurpriseAgent
from agents.insider_trading_signal_agent import InsiderTradingSignalAgent
from agents.intraday_order_book_imbalance_agent import IntradayOrderBookImbalanceAgent
from agents.intraday_volume_spike_agent import IntradayVolumeSpikeAgent
from agents.unusual_options_volume_agent import UnusualOptionsVolumeAgent
from agents.crypto_stablecoin_premium_agent import CryptoStablecoinPremiumAgent
from agents.distressed_property_agent import DistressedPropertyAgent
from agents.code_guardian_agent import CodeGuardianAgent
from agents.cta_flows_agent import CTAFlowsAgent
"""
Market Inefficiency Detection Agents

This module contains various AI agents for detecting market anomalies
and inefficiencies across different asset classes and data sources.
"""

import importlib
import logging
from typing import Type, Optional, List
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

# Available agent classes
AVAILABLE_AGENTS = [
    "CryptoStablecoinPremiumAgent",
    "UnusualOptionsVolumeAgent",
    "IntradayVolumeSpikeAgent",
    "IntradayOrderBookImbalanceAgent",
    "InsiderTradingSignalAgent",
    "EarningsWhisperSurpriseAgent",
    "IntradayVolatilitySpikeAgent",
    "EarningsSurpriseDriftAgent",
    'MacroWatcherAgent',
    'WhaleWalletWatcherAgent',
    'ArbitrageFinderAgent',
    'SentimentDivergenceAgent',
    'AltDataSignalAgent',
    'EquityMomentumAgent',
    'CryptoFundingRateAgent',
    'BondStressAgent',
    'GeopoliticalRiskAgent',
    'MarketCorrectionAgent',
    'HeartbeatAgent',
    'GreatestTradeAgent',
    'DailyPredictionAgent',
    'CryptoPredictionAgent',
    'TechnicalAnalysisAgent',
    'DistressedPropertyAgent',
    'DatedBasisAgent',
    'CodeGuardianAgent',
    'CTAFlowsAgent',
    'TalebFragilityAgent',
    'SpitznagelSafeHavenAgent',
    'SimonsPatternAgent',
    'AssnessFactorAgent',
    'AntifragileBoardAgent',
]

# Antifragile Board agents (loaded from antifragile module, not agents/)
ANTIFRAGILE_AGENT_CLASSES = {
    'TalebFragilityAgent': 'antifragile.agents',
    'SpitznagelSafeHavenAgent': 'antifragile.agents',
    'SimonsPatternAgent': 'antifragile.agents',
    'AssnessFactorAgent': 'antifragile.agents',
    'AntifragileBoardAgent': 'antifragile.agents',
}


def get_agent_class(agent_name: str) -> Optional[Type[BaseAgent]]:
    """
    Dynamically import and return an agent class by name

    Args:
        agent_name: Name of the agent class

    Returns:
        Agent class or None if not found
    """
    # Check if this is an antifragile board agent first
    if agent_name in ANTIFRAGILE_AGENT_CLASSES:
        try:
            module = importlib.import_module(ANTIFRAGILE_AGENT_CLASSES[agent_name])
            agent_class = getattr(module, agent_name)
            if issubclass(agent_class, BaseAgent):
                return agent_class
        except (ImportError, AttributeError) as e:
            logger.error(f"Could not import antifragile agent {agent_name}: {e}")
            return None

    try:
        # Convert agent name to module name (snake_case)
        module_name = ''.join([
            '_' + c.lower() if c.isupper() else c for c in agent_name
        ]).lstrip('_')

        # Import the module
        module = importlib.import_module(f'agents.{module_name}')

        # Get the agent class
        agent_class = getattr(module, agent_name)

        # Verify it's a BaseAgent subclass
        if issubclass(agent_class, BaseAgent):
            return agent_class
        else:
            logger.error(f"{agent_name} is not a BaseAgent subclass")
            return None

    except ImportError as e:
        logger.error(f"Could not import agent {agent_name}: {e}")
        return None
    except AttributeError as e:
        logger.error(f"Agent class {agent_name} not found in module: {e}")
        return None


def get_all_agents() -> List[Type[BaseAgent]]:
    """
    Get all available agent classes
    
    Returns:
        List of agent classes
    """
    agents = []
    for agent_name in AVAILABLE_AGENTS:
        agent_class = get_agent_class(agent_name)
        if agent_class:
            agents.append(agent_class)
    return agents


def create_agent(agent_name: str) -> Optional[BaseAgent]:
    """
    Create an instance of an agent by name
    
    Args:
        agent_name: Name of the agent class
        
    Returns:
        Agent instance or None if creation failed
    """
    agent_class = get_agent_class(agent_name)
    if agent_class:
        try:
            return agent_class()
        except Exception as e:
            logger.error(f"Error creating agent {agent_name}: {e}")
            return None
    return None
