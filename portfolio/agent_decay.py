"""
Agent Decay Curves

Smoothly fades agent capital allocation based on recent performance.
Prevents abrupt disable / enable behavior.
"""

import math
from typing import Dict


class AgentDecayModel:
    def __init__(
        self,
        half_life_days: float = 30.0,
        min_floor: float = 0.05,
        recovery_rate: float = 0.02
    ):
        self.half_life_days = half_life_days
        self.min_floor = min_floor
        self.recovery_rate = recovery_rate

    def decay_factor(
        self,
        score: float,
        days_since_eval: float
    ) -> float:
        """
        score: normalized agent performance (e.g. Sharpe, mean return)
        days_since_eval: time since last evaluation window
        
        Returns decay_factor in [min_floor, 1.0]
        """
        if score < 0:
            decay = math.exp(
                math.log(0.5) * days_since_eval / self.half_life_days
            )
            return max(decay, self.min_floor)

        recovery = min(
            1.0,
            self.min_floor + (1.0 - self.min_floor) *
            (1 - math.exp(-self.recovery_rate * days_since_eval))
        )
        return recovery
