from collections import defaultdict
import numpy as np

class AgentFailureHeatmap:
    """
    Records agent performance across different market regimes.
    Visualizes as a heatmap to identify which agents fail first during regime transitions.
    """
    def __init__(self, history_length=100):
        self.history_length = history_length
        self.agent_performance = defaultdict(lambda: defaultdict(list))
        self.regime_history = []
        
    def update(self, agent: str, regime: str, performance_score: float):
        """Update agent performance for a specific regime."""
        self.regime_history.append(regime)
        self.regime_history = self.regime_history[-self.history_length:]
        
        perf_list = self.agent_performance[agent][regime]
        perf_list.append(performance_score)
        if len(perf_list) > self.history_length:
            self.agent_performance[agent][regime] = perf_list[-self.history_length:]
    
    def get_heatmap_data(self):
        """Return heatmap data: avg performance across agents and regimes."""
        result = {}
        all_regimes = set()
        
        for agent, regimes in self.agent_performance.items():
            all_regimes.update(regimes.keys())
        
        for agent, regimes in self.agent_performance.items():
            result[agent] = {}
            for regime in all_regimes:
                scores = regimes.get(regime, [])
                if scores:
                    avg = sum(scores) / len(scores)
                    result[agent][regime] = {
                        "avg": round(avg, 2),
                        "count": len(scores),
                        "recent": scores[-10:] if len(scores) > 10 else scores,
                    }
                else:
                    result[agent][regime] = {"avg": 0, "count": 0, "recent": []}
        
        return {
            "agents": result,
            "regimes": list(all_regimes),
            "recent_regime_history": self.regime_history[-20:],
        }

    def get_failure_rates(self):
        """Calculate failure rate per agent per regime (performance < threshold)."""
        threshold = 1.0
        result = {}
        
        for agent, regimes in self.agent_performance.items():
            result[agent] = {}
            for regime, scores in regimes.items():
                if scores:
                    failures = sum(1 for s in scores if s < threshold)
                    result[agent][regime] = round(failures / len(scores), 2)
                else:
                    result[agent][regime] = 0.0
        
        return result


_failure_heatmap = AgentFailureHeatmap()
