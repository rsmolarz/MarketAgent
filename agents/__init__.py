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
    'MacroWatcherAgent',
    'WhaleWalletWatcherAgent', 
    'ArbitrageFinderAgent',
    'SentimentDivergenceAgent',
    'AltDataSignalAgent',
    'EquityMomentumAgent',
    'CryptoFundingRateAgent',
    'BondStressAgent'
]

def get_agent_class(agent_name: str) -> Optional[Type[BaseAgent]]:
    """
    Dynamically import and return an agent class by name
    
    Args:
        agent_name: Name of the agent class
        
    Returns:
        Agent class or None if not found
    """
    try:
        # Convert agent name to module name (snake_case)
        module_name = ''.join(['_' + c.lower() if c.isupper() else c for c in agent_name]).lstrip('_')
        
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
