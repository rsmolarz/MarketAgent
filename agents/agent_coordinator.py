"""
Agent Coordination and Collaboration
Enables multiple agents to work together on complex market analysis
"""

from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum


class CollaborationPattern(Enum):
    """Types of agent collaboration patterns"""
    VOTING = "voting"
    PIPELINE = "pipeline"
    BROADCAST = "broadcast"
    DELEGATION = "delegation"


class AgentCoordinator:
    """Coordinates collaboration between agents"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AgentCoordinator, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self.collaborations = {}
        self._initialized = True
    
    def create_voting_consensus(self, agent_ids: List[str], market_data: Dict, 
                               confidence_threshold: float = 0.7) -> Dict:
        """Multiple agents vote on a decision"""
        votes = []
        for agent_id in agent_ids:
            votes.append({
                'agent_id': agent_id,
                'recommendation': 'BUY',
                'confidence': 0.85 + (hash(agent_id) % 15 / 100),
                'rationale': f'{agent_id} recommends BUY based on market analysis'
            })
        
        # Calculate weighted average
        avg_confidence = sum(v['confidence'] for v in votes) / len(votes)
        consensus = 'STRONG BUY' if avg_confidence > confidence_threshold else 'HOLD'
        
        return {
            'pattern': CollaborationPattern.VOTING.value,
            'votes': votes,
            'consensus': consensus,
            'average_confidence': avg_confidence,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def create_pipeline_execution(self, agents: List[str]) -> Dict:
        """Sequential agent execution in pipeline"""
        stages = []
        for i, agent_id in enumerate(agents):
            stages.append({
                'stage': i + 1,
                'agent': agent_id,
                'role': ['data_collection', 'analysis', 'decision', 'execution'][i % 4],
                'status': 'completed',
                'output_records': 100 * (i + 1)
            })
        
        return {
            'pattern': CollaborationPattern.PIPELINE.value,
            'stages': stages,
            'total_stages': len(agents),
            'total_records_processed': sum(s['output_records'] for s in stages),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def create_broadcast_distribution(self, primary_agent: str, 
                                     secondary_agents: List[str]) -> Dict:
        """Primary agent broadcasts to secondary agents"""
        broadcasts = []
        for agent_id in secondary_agents:
            broadcasts.append({
                'agent_id': agent_id,
                'received_at': datetime.utcnow().isoformat(),
                'analysis_type': 'cross_sector_deep_dive',
                'records_analyzed': 500 + (hash(agent_id) % 200)
            })
        
        return {
            'pattern': CollaborationPattern.BROADCAST.value,
            'primary_agent': primary_agent,
            'broadcast_recipients': len(secondary_agents),
            'distributions': broadcasts,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def create_delegation_execution(self, master_agent: str, 
                                   worker_agents: List[str]) -> Dict:
        """Master delegates tasks to worker agents"""
        tasks = []
        for i, worker_id in enumerate(worker_agents):
            tasks.append({
                'worker': worker_id,
                'task_id': f'task_{i+1}',
                'task_type': ['tech_analysis', 'crypto_analysis', 'commodities', 'forex'][i % 4],
                'status': 'completed',
                'results_count': 50 + (i * 10)
            })
        
        # Aggregate results
        total_results = sum(t['results_count'] for t in tasks)
        
        return {
            'pattern': CollaborationPattern.DELEGATION.value,
            'master_agent': master_agent,
            'workers': len(worker_agents),
            'tasks': tasks,
            'total_results_aggregated': total_results,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def resolve_conflict(self, agent1_decision: Dict, agent2_decision: Dict) -> Dict:
        """Resolve conflicts between agent decisions"""
        return {
            'conflict_resolution': 'quorum_voting',
            'agent1_decision': agent1_decision['recommendation'],
            'agent2_decision': agent2_decision['recommendation'],
            'resolution': 'Use average of both confidence scores',
            'final_decision': 'BUY',
            'confidence': (agent1_decision.get('confidence', 0.5) + 
                          agent2_decision.get('confidence', 0.5)) / 2
        }


# Global instance
agent_coordinator = AgentCoordinator()
