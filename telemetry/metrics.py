from prometheus_client import Counter, Histogram, Gauge

AGENT_RUNS = Counter("agent_runs_total", "Total agent runs", ["agent"])
AGENT_ERRORS = Counter("agent_errors_total", "Total agent errors", ["agent"])
AGENT_LATENCY_MS = Histogram("agent_latency_ms", "Agent latency (ms)", ["agent"], buckets=(50, 100, 250, 500, 1000, 2000, 5000, 10000))
AGENT_COST_USD = Histogram("agent_cost_usd", "Agent cost (USD)", ["agent"], buckets=(0.0005, 0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1))
AGENT_REWARD = Histogram("agent_reward", "Agent reward", ["agent"], buckets=(-2, -1, -0.5, -0.2, 0, 0.1, 0.2, 0.5, 1, 2))

AGENT_LAST_REWARD = Gauge("agent_last_reward", "Last reward", ["agent"])
AGENT_LAST_COST_USD = Gauge("agent_last_cost_usd", "Last cost (USD)", ["agent"])
AGENT_LAST_LATENCY_MS = Gauge("agent_last_latency_ms", "Last latency (ms)", ["agent"])

AGENT_REWARD_MEAN = Gauge("agent_reward_mean", "Rolling mean reward", ["agent"])
AGENT_REWARD_STD = Gauge("agent_reward_std", "Rolling stddev reward", ["agent"])
AGENT_REWARD_SHARPE = Gauge("agent_reward_sharpe", "Rolling Sharpe-like (mean/std)", ["agent"])
AGENT_DRAWDOWN = Gauge("agent_reward_drawdown", "Rolling drawdown (peak-to-trough) using reward proxy", ["agent"])
AGENT_QUARANTINED = Gauge("agent_quarantined", "1 if quarantined else 0", ["agent"])
