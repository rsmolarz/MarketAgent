"""
Consensus mechanism for multi-agent agreement.

Implements bitmask-tracked barrier synchronization with confidence-weighted
hybrid voting (TA numerical scores + LLM directional opinions).
"""

from agents.consensus.aggregator import AgentFlags, BitmaskBarrier, HybridVotingAggregator
from agents.consensus.council_voter import LLMCouncilVoter

__all__ = ["AgentFlags", "BitmaskBarrier", "HybridVotingAggregator", "LLMCouncilVoter"]
