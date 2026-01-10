from collections import defaultdict, deque
from math import exp
import numpy as np
import io
import base64
import logging

logger = logging.getLogger(__name__)


class AgentDecayModel:
    """
    Exponential decay on agent performance.
    Decay accelerates when uncertainty is high.
    Supports tunable decay rates per agent and uncertainty-aware adjustment.
    """
    def __init__(self, half_life=200, default_decay_rate=1.0):
        self.half_life = half_life
        self.default_decay_rate = default_decay_rate
        self.agent_decay_rates = {}
        self.history = defaultdict(lambda: deque(maxlen=1000))
        self.uncertainty_history = defaultdict(lambda: deque(maxlen=1000))

    def get_decay_rate(self, agent: str) -> float:
        """Get the decay rate for a specific agent"""
        return self.agent_decay_rates.get(agent, self.default_decay_rate)

    def update(self, agent, reward, uncertainty=0.0):
        agent_rate = self.get_decay_rate(agent)
        uncertainty_multiplier = 1 + uncertainty
        decay_lambda = (0.693 / self.half_life) * agent_rate * uncertainty_multiplier
        prev = self.history[agent][-1] if self.history[agent] else 1.0
        decayed = prev * exp(-decay_lambda) + reward
        self.history[agent].append(decayed)
        self.uncertainty_history[agent].append(uncertainty)
        return decayed

    def get(self, agent: str) -> float:
        """Return the current decay multiplier for the agent"""
        if not self.history[agent]:
            return 1.0
        return self.history[agent][-1]

    def set(self, agent: str, value: float):
        """Manually set decay for an agent"""
        self.history[agent].append(value)

    def get_uncertainty(self, agent: str) -> float:
        """Return the current uncertainty level for the agent"""
        if not self.uncertainty_history[agent]:
            return 0.0
        return self.uncertainty_history[agent][-1]

    def series(self, agent, last_n=100):
        return list(self.history[agent])[-last_n:]

    def uncertainty_series(self, agent, last_n=100):
        return list(self.uncertainty_history[agent])[-last_n:]

    def all_series(self, last_n=100):
        return {
            agent: self.series(agent, last_n)
            for agent in self.history.keys()
        }

    def tune_decay_rate(self, agent: str, new_rate: float):
        """
        Tune the decay rate for a specific agent based on performance.
        Values <1.0 slow decay, values >1.0 accelerate decay.
        """
        self.agent_decay_rates[agent] = max(0.01, min(2.0, new_rate))

    def compute_uncertainty_band(self, agent: str, last_n=100, band_width=0.1):
        """
        Compute uncertainty bands around the decay series.
        Returns (decay_values, upper_band, lower_band)
        """
        decay_vals = np.array(self.series(agent, last_n))
        if len(decay_vals) == 0:
            return np.array([1.0]), np.array([1.0 + band_width]), np.array([1.0 - band_width])
        
        uncertainty_vals = np.array(self.uncertainty_series(agent, last_n))
        if len(uncertainty_vals) == 0:
            uncertainty_vals = np.zeros_like(decay_vals)
        
        dynamic_band = band_width * (1 + uncertainty_vals[:len(decay_vals)])
        upper = decay_vals + dynamic_band
        lower = np.maximum(0, decay_vals - dynamic_band)
        
        return decay_vals, upper, lower


def generate_decay_chart(spy_data, agents, decay_model, period_days=252):
    """
    Generate SPY price vs agent decay chart with uncertainty bands.
    Returns base64 encoded PNG image.
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    
    fig, ax1 = plt.subplots(figsize=(14, 7))
    
    spy_close = spy_data['Close'].iloc[-period_days:] if len(spy_data) > period_days else spy_data['Close']
    dates = spy_close.index
    
    ax1.plot(dates, spy_close.values, label='SPY Price', color='#2563eb', linewidth=2, alpha=0.8)
    ax1.set_xlabel('Date', fontsize=12)
    ax1.set_ylabel('SPY Price ($)', color='#2563eb', fontsize=12)
    ax1.tick_params(axis='y', labelcolor='#2563eb')
    ax1.grid(True, alpha=0.3, linestyle='--')
    
    ax2 = ax1.twinx()
    
    colors = ['#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4']
    
    for i, agent in enumerate(agents):
        color = colors[i % len(colors)]
        
        decay_vals, upper, lower = decay_model.compute_uncertainty_band(agent, last_n=period_days)
        
        if len(decay_vals) < len(dates):
            decay_vals = np.pad(decay_vals, (len(dates) - len(decay_vals), 0), 
                               mode='constant', constant_values=1.0)
            upper = np.pad(upper, (len(dates) - len(upper), 0), 
                          mode='constant', constant_values=1.1)
            lower = np.pad(lower, (len(dates) - len(lower), 0), 
                          mode='constant', constant_values=0.9)
        elif len(decay_vals) > len(dates):
            decay_vals = decay_vals[-len(dates):]
            upper = upper[-len(dates):]
            lower = lower[-len(dates):]
        
        ax2.plot(dates, decay_vals, label=f'{agent} Decay', 
                color=color, linewidth=1.5, alpha=0.8)
        
        ax2.fill_between(dates, lower, upper, color=color, alpha=0.15,
                        label=f'{agent} Uncertainty')
    
    ax2.set_ylabel('Agent Decay Score', fontsize=12)
    ax2.set_ylim(0, 1.5)
    
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', 
              fontsize=9, framealpha=0.9)
    
    plt.title('SPY Price vs Agent Decay with Uncertainty Bands', fontsize=14, fontweight='bold')
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    buf.seek(0)
    plt.close(fig)
    
    return base64.b64encode(buf.getvalue()).decode('utf-8')


_decay = AgentDecayModel()


# Regime-Specific Half-Life Configuration
REGIME_HALF_LIFE = {
    "risk_on": 120,
    "risk_off": 40,
    "transition": 20,
    "shock": 10,
    "unknown": 60,
}


def decay_multiplier(age_steps: int, regime: str) -> float:
    """
    Calculate decay multiplier for agent score based on age and regime.
    
    Args:
        age_steps: Number of time steps since agent started tracking
        regime: Current market regime (risk_on, risk_off, transition, shock, unknown)
    
    Returns:
        Decay multiplier between 0 and 1
    """
    half_life = REGIME_HALF_LIFE.get(regime, 60)
    return exp(-age_steps / half_life)


def get_decay_curve(regime: str, max_steps: int = 200) -> list:
    """
    Get decay curve data points for visualization.
    """
    return [
        {"step": s, "decay": round(decay_multiplier(s, regime), 4)}
        for s in range(0, max_steps, 5)
    ]


def get_all_decay_curves(max_steps: int = 200) -> dict:
    """
    Get decay curves for all regimes for comparison visualization.
    """
    return {
        regime: get_decay_curve(regime, max_steps)
        for regime in REGIME_HALF_LIFE.keys()
    }


def get_decay_info() -> dict:
    """
    Get decay configuration info for reporting.
    """
    return {
        "half_lives": REGIME_HALF_LIFE.copy(),
        "description": "Exponential decay multiplier applied to agent scores based on regime"
    }
