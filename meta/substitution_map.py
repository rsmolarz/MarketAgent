"""
Agent Substitution Map (Regime-Aware)

When an agent decays below a threshold in a given regime, the system:
1. Identifies which agents historically perform better in that same regime
2. Promotes the best substitute
3. Gradually shifts capital / cadence
4. Logs why the substitution happened

This prevents:
- Dead zones
- Regime blind spots
- Allocator oscillation
- "All agents off" failure modes
"""

from collections import defaultdict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SubstitutionMap:
    """
    Data-driven agent substitution mapping.
    
    Learns from decay heatmap and performance data to recommend
    replacements when an agent fails in a specific regime.
    """
    
    def __init__(self, min_samples: int = 25, decay_threshold: float = 0.3, strong_threshold: float = 0.6):
        self.min_samples = min_samples
        self.decay_threshold = decay_threshold
        self.strong_threshold = strong_threshold
        self.map = defaultdict(dict)
        self.last_built = None
    
    def build(self, decay_heatmap_summary: dict, performance_by_regime: dict = None):
        """
        Build substitution map from decay heatmap and performance data.
        
        Args:
            decay_heatmap_summary: {regime: {agent: mean_decay}}
            performance_by_regime: {regime: {agent: mean_forward_return}} (optional)
        """
        if performance_by_regime is None:
            performance_by_regime = {}
        
        self.map.clear()
        
        for regime, decays in decay_heatmap_summary.items():
            perf = performance_by_regime.get(regime, {})
            
            for failed_agent, decay in decays.items():
                if decay >= self.decay_threshold:
                    continue
                
                candidates = []
                for agent, agent_decay in decays.items():
                    if agent == failed_agent:
                        continue
                    if agent_decay < self.strong_threshold:
                        continue
                    
                    score = agent_decay
                    if agent in perf:
                        score += perf[agent] * 0.5
                    
                    candidates.append((agent, score, agent_decay))
                
                candidates.sort(key=lambda x: x[1], reverse=True)
                
                if candidates:
                    self.map[regime][failed_agent] = [
                        {
                            'agent': c[0],
                            'score': round(c[1], 3),
                            'decay': round(c[2], 3)
                        }
                        for c in candidates[:3]
                    ]
        
        self.last_built = datetime.utcnow()
        logger.info(f"Substitution map rebuilt: {sum(len(v) for v in self.map.values())} substitutions across {len(self.map)} regimes")
    
    def get_substitute(self, regime: str, agent: str) -> list:
        """
        Get substitution candidates for an agent in a regime.
        
        Returns:
            List of {'agent': name, 'score': float, 'decay': float} or None
        """
        return self.map.get(regime, {}).get(agent)
    
    def get_best_substitute(self, regime: str, agent: str) -> tuple:
        """
        Get the single best substitute for an agent.
        
        Returns:
            (substitute_agent_name, score) or (None, None)
        """
        subs = self.get_substitute(regime, agent)
        if subs and len(subs) > 0:
            best = subs[0]
            return (best['agent'], best['score'])
        return (None, None)
    
    def should_substitute(self, regime: str, agent: str, current_decay: float) -> bool:
        """
        Check if agent should be substituted based on current decay.
        """
        if current_decay >= self.decay_threshold:
            return False
        
        return self.get_substitute(regime, agent) is not None
    
    def apply_to_scores(self, scores: dict, regime: str, decay_values: dict) -> dict:
        """
        Apply substitution logic to allocator scores.
        
        When a failing agent is detected:
        - Boost best substitute by 50% of failing agent's absolute score
        - Reduce failing agent's score to 20%
        
        Args:
            scores: {agent: score} from allocator
            regime: Current market regime
            decay_values: {agent: decay_value}
        
        Returns:
            Modified scores dict
        """
        modified = scores.copy()
        
        for agent, decay in decay_values.items():
            if decay >= self.decay_threshold:
                continue
            
            subs = self.get_substitute(regime, agent)
            if not subs:
                continue
            
            best_alt = subs[0]['agent']
            
            if best_alt in modified and agent in modified:
                boost = abs(modified[agent]) * 0.5
                modified[best_alt] = modified.get(best_alt, 0) + boost
                modified[agent] *= 0.2
                
                logger.debug(f"Substitution applied: {agent} -> {best_alt} in {regime}")
        
        return modified
    
    def get_substitution_report(self) -> dict:
        """
        Get a complete report of all substitution mappings.
        
        Returns:
            {
                'last_built': timestamp,
                'total_substitutions': count,
                'by_regime': {regime: [{from_agent, to_agents: [...]}]}
            }
        """
        report = {
            'last_built': self.last_built.isoformat() if self.last_built else None,
            'total_substitutions': sum(len(v) for v in self.map.values()),
            'by_regime': {}
        }
        
        for regime, subs in self.map.items():
            report['by_regime'][regime] = [
                {
                    'from_agent': failed,
                    'to_agents': candidates
                }
                for failed, candidates in subs.items()
            ]
        
        return report
    
    def get_substitutions_for_regime(self, regime: str) -> list:
        """
        Get all substitutions for a specific regime (for dashboard display).
        
        Returns:
            [
                {
                    'failed_agent': str,
                    'substitute': str,
                    'confidence': 'high'|'medium'|'low',
                    'decay': float
                }
            ]
        """
        regime_subs = self.map.get(regime, {})
        result = []
        
        for failed_agent, candidates in regime_subs.items():
            if candidates:
                best = candidates[0]
                confidence = 'high' if best['score'] > 0.8 else ('medium' if best['score'] > 0.5 else 'low')
                result.append({
                    'failed_agent': failed_agent,
                    'substitute': best['agent'],
                    'confidence': confidence,
                    'decay': best['decay']
                })
        
        return result


substitution_map = SubstitutionMap()
