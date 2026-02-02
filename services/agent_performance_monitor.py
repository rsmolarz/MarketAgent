"""Agent Performance Monitor

Tracks agent execution metrics, failures, and performance to ensure
reliability and detect issues before they impact the platform.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import time

logger = logging.getLogger(__name__)


@dataclass
class AgentMetrics:
    """Metrics for a single agent"""
    agent_name: str
    last_execution: datetime
    execution_count: int = 0
    error_count: int = 0
    average_execution_time: float = 0.0
    last_error: Optional[str] = None
    status: str = "idle"  # idle, running, failed, healthy
    health_score: float = 1.0  # 0.0 to 1.0


class AgentPerformanceMonitor:
    """Monitors agent performance and detects failures"""
    
    def __init__(self):
        self.metrics: Dict[str, AgentMetrics] = {}
        self.execution_times: Dict[str, List[float]] = {}
        self.alert_threshold = 0.8  # Alert if success rate < 80%
        self.retry_max_attempts = 3

    def record_execution(self, agent_name: str, execution_time: float, success: bool, error: Optional[str] = None):
        """Record agent execution metrics"""
        if agent_name not in self.metrics:
            self.metrics[agent_name] = AgentMetrics(
                agent_name=agent_name,
                last_execution=datetime.utcnow()
            )
        
        if agent_name not in self.execution_times:
            self.execution_times[agent_name] = []
        
        metrics = self.metrics[agent_name]
        metrics.execution_count += 1
        metrics.last_execution = datetime.utcnow()
        
        # Track execution time
        self.execution_times[agent_name].append(execution_time)
        if len(self.execution_times[agent_name]) > 100:
            self.execution_times[agent_name].pop(0)
        
        # Update average
        metrics.average_execution_time = sum(self.execution_times[agent_name]) / len(self.execution_times[agent_name])
        
        # Handle failures
        if not success:
            metrics.error_count += 1
            metrics.last_error = error
            metrics.status = "failed"
            self._update_health_score(agent_name)
        else:
            metrics.status = "healthy"
            self._update_health_score(agent_name)
        
        logger.debug(f"Recorded execution for {agent_name}: success={success}, time={execution_time:.2f}s")

    def _update_health_score(self, agent_name: str):
        """Update agent health score based on recent performance"""
        metrics = self.metrics[agent_name]
        if metrics.execution_count == 0:
            metrics.health_score = 1.0
            return
        
        success_rate = 1.0 - (metrics.error_count / metrics.execution_count)
        metrics.health_score = max(0.0, min(1.0, success_rate))
        
        if metrics.health_score < self.alert_threshold:
            logger.warning(f"Agent {agent_name} health score below threshold: {metrics.health_score:.2f}")

    def get_agent_metrics(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Get metrics for a specific agent"""
        if agent_name not in self.metrics:
            return None
        return asdict(self.metrics[agent_name])

    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all agents"""
        return {name: asdict(m) for name, m in self.metrics.items()}

    def get_unhealthy_agents(self) -> List[str]:
        """Get list of agents with health score below threshold"""
        return [
            name for name, m in self.metrics.items()
            if m.health_score < self.alert_threshold
        ]

    def get_failed_agents(self) -> List[str]:
        """Get list of agents currently in failed state"""
        return [
            name for name, m in self.metrics.items()
            if m.status == "failed"
        ]

    def reset_agent_metrics(self, agent_name: str):
        """Reset metrics for a specific agent"""
        if agent_name in self.metrics:
            del self.metrics[agent_name]
        if agent_name in self.execution_times:
            del self.execution_times[agent_name]
        logger.info(f"Reset metrics for agent {agent_name}")

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get overall performance summary"""
        total_agents = len(self.metrics)
        healthy_agents = sum(1 for m in self.metrics.values() if m.health_score >= self.alert_threshold)
        failed_agents = sum(1 for m in self.metrics.values() if m.status == "failed")
        
        avg_health = sum(m.health_score for m in self.metrics.values()) / total_agents if total_agents > 0 else 1.0
        
        return {
            "total_agents": total_agents,
            "healthy_agents": healthy_agents,
            "failed_agents": failed_agents,
            "average_health_score": round(avg_health, 2),
            "unhealthy_agents": self.get_unhealthy_agents(),
            "timestamp": datetime.utcnow().isoformat()
        }


# Global instance
performance_monitor = AgentPerformanceMonitor()
