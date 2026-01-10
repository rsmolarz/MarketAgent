import json
import math
from pathlib import Path
from collections import defaultdict, deque

from telemetry.metrics import (
    AGENT_REWARD_MEAN, AGENT_REWARD_STD, AGENT_REWARD_SHARPE,
    AGENT_DRAWDOWN, AGENT_QUARANTINED
)

EVENTS = Path("telemetry/events.jsonl")


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def _std(xs):
    if not xs or len(xs) < 2:
        return 0.0
    m = _mean(xs)
    v = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
    return math.sqrt(max(v, 0.0))


def _drawdown(xs):
    if not xs:
        return 0.0
    equity = 0.0
    peak = 0.0
    dd = 0.0
    for r in xs:
        equity += r
        peak = max(peak, equity)
        dd = min(dd, equity - peak)
    return dd


def update_prom_metrics(window=500, last_n=5000, quarantine_set=None):
    quarantine_set = quarantine_set or set()

    if not EVENTS.exists():
        return

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

    for agent, dq in by.items():
        xs = list(dq)
        m = _mean(xs)
        s = _std(xs)
        sharpe = (m / s) if s > 1e-9 else 0.0
        dd = _drawdown(xs)

        AGENT_REWARD_MEAN.labels(agent).set(m)
        AGENT_REWARD_STD.labels(agent).set(s)
        AGENT_REWARD_SHARPE.labels(agent).set(sharpe)
        AGENT_DRAWDOWN.labels(agent).set(dd)
        AGENT_QUARANTINED.labels(agent).set(1.0 if agent in quarantine_set else 0.0)
