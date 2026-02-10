import json
from pathlib import Path
from collections import defaultdict, deque

from services.quarantine import quarantine, clear_quarantine, quarantined_agents
from telemetry.rolling_stats import update_prom_metrics

EVENTS = Path("telemetry/events.jsonl")

EXEMPT_AGENTS = {
    'CodeGuardianAgent', 'HealthCheckAgent', 'MetaSupervisorAgent',
}


def compute_drawdown(rewards):
    equity = 0.0
    peak = 0.0
    dd = 0.0
    for r in rewards:
        equity += r
        peak = max(peak, equity)
        dd = min(dd, equity - peak)
    return dd


def run(window=500, last_n=5000, dd_limit=-10.0, sharpe_floor=-0.05):
    if not EVENTS.exists():
        return {"ok": True, "quarantined": [], "cleared": []}

    lines = EVENTS.read_text().splitlines()[-last_n:]
    by = defaultdict(lambda: deque(maxlen=window))

    for ln in lines:
        try:
            e = json.loads(ln)
        except Exception:
            continue
        a = e.get("agent")
        r = e.get("reward")
        if a and r is not None:
            try:
                by[a].append(float(r))
            except Exception:
                pass

    q_before = set(quarantined_agents().keys())
    q_now = set()

    for agent, dq in by.items():
        if agent in EXEMPT_AGENTS:
            if agent in q_before:
                clear_quarantine(agent)
            continue

        rs = list(dq)
        dd = compute_drawdown(rs)

        if dd <= dd_limit:
            quarantine(agent, f"Auto-quarantine: drawdown {dd:.3f} <= limit {dd_limit}")
            q_now.add(agent)
        else:
            if agent in q_before:
                clear_quarantine(agent)

    update_prom_metrics(window=window, last_n=last_n, quarantine_set=q_now)

    return {"ok": True, "quarantined": list(q_now), "cleared": [a for a in q_before if a not in q_now]}
