import json
from pathlib import Path
from math import log, sqrt, exp
from collections import defaultdict, deque
from meta.decay import _decay as agent_decay_model, decay_multiplier

EVENTS = Path("telemetry/events.jsonl")


class UCBAllocator:
    """
    Uncertainty-aware UCB allocator with agent decay curves.

    Key properties:
    - Capital fades smoothly when agents stop working
    - Exploration is damped during uncertainty
    - No abrupt disable unless upstream policy says so
    """

    def __init__(
        self,
        window=500,
        exploration=1.5,
        half_life=200,
        min_decay=0.15
    ):
        self.window = window
        self.exploration = exploration
        self.half_life = half_life
        self.min_decay = min_decay

        self.rewards = defaultdict(lambda: deque(maxlen=window))
        self.counts = defaultdict(int)
        self.last_positive = defaultdict(lambda: None)

        self.global_decay_multiplier = 1.0

    def ingest_events(self, last_n=5000):
        if not EVENTS.exists():
            return

        for ln in EVENTS.read_text().splitlines()[-last_n:]:
            try:
                e = json.loads(ln)
            except Exception:
                continue

            agent = e.get("agent")
            reward = e.get("reward")

            if agent and reward is not None:
                r = float(reward)
                self.rewards[agent].append(r)
                self.counts[agent] += 1

                if r > 0:
                    self.last_positive[agent] = self.counts[agent]

    def _decay_factor(self, agent: str) -> float:
        """
        Exponential decay based on distance from last positive outcome.
        """
        last_good = self.last_positive.get(agent)
        if last_good is None:
            return self.min_decay

        age = max(self.counts[agent] - last_good, 0)
        decay = exp(-log(2) * age / max(self.half_life, 1))

        return max(decay, self.min_decay)

    def _agent_model_decay(self, agent: str) -> float:
        """
        Get decay from AgentDecayModel based on recent performance history.
        Returns normalized decay in [0, 1] range.
        """
        series = agent_decay_model.series(agent, last_n=10)
        if not series or len(series) < 2:
            return 1.0
        
        max_val = max(series) if max(series) > 0 else 1.0
        current = series[-1] if series else 0.0
        
        return min(1.0, max(self.min_decay, current / max_val))

    def score(self, agent: str, total_pulls: int, uncertainty: float = 0.0, regime: str = "unknown") -> float:
        rs = self.rewards[agent]
        n = max(self.counts[agent], 1)

        mean = sum(rs) / len(rs) if rs else 0.0

        bonus = self.exploration * sqrt(log(max(total_pulls, 2)) / n)

        internal_decay = self._decay_factor(agent)
        model_decay = self._agent_model_decay(agent)
        
        age = len(self.rewards[agent])
        regime_decay = decay_multiplier(age, regime)
        
        uncertainty_decay = max(0.2, 1.0 - uncertainty)
        
        decay = internal_decay * model_decay * regime_decay * self.global_decay_multiplier * uncertainty_decay

        return decay * (mean + bonus)

    def allocate(
        self,
        agents,
        min_runs=None,
        max_runs=None,
        total_budget_runs=100,
        uncertainty_decay=1.0,
        agent_uncertainty=None,
        regime: str = "unknown"
    ):
        """
        uncertainty_decay:
          global decay passed from scheduler (e.g. 0.4 during shocks)
        agent_uncertainty:
          per-agent uncertainty dict from LLM council disagreement
        regime:
          current market regime for regime-specific decay
        """
        min_runs = min_runs or {}
        max_runs = max_runs or {}
        agent_uncertainty = agent_uncertainty or {}

        self.global_decay_multiplier = float(uncertainty_decay)

        try:
            from meta.redundancy import find_redundant_agents
            redundant = find_redundant_agents()
        except Exception:
            redundant = set()

        total_pulls = sum(self.counts[a] for a in agents) + 1
        
        REDUNDANCY_PENALTY = 0.3
        scores = {}
        for a in agents:
            base_score = self.score(a, total_pulls, agent_uncertainty.get(a, 0.0), regime)
            if a in redundant:
                scores[a] = base_score * REDUNDANCY_PENALTY
            else:
                scores[a] = base_score

        quotas = {a: int(min_runs.get(a, 0)) for a in agents}
        remaining = max(total_budget_runs - sum(quotas.values()), 0)

        ranked = sorted(agents, key=lambda a: scores[a], reverse=True)

        i = 0
        while remaining > 0 and ranked:
            a = ranked[i % len(ranked)]
            if quotas[a] < int(max_runs.get(a, total_budget_runs)):
                quotas[a] += 1
                remaining -= 1
            i += 1

        return quotas, scores
