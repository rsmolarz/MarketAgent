import json
from pathlib import Path
from collections import defaultdict

LOG = Path("telemetry/uncertainty_events.jsonl")


def load_recent_uncertainty(last_n: int = 500) -> dict:
    """
    Load recent uncertainty scores per agent.
    Returns: {agent_name: average_uncertainty}
    """
    if not LOG.exists():
        return {}
    
    acc = defaultdict(list)
    
    try:
        lines = LOG.read_text().splitlines()[-last_n:]
        for ln in lines:
            if not ln.strip():
                continue
            try:
                e = json.loads(ln)
                agent = e.get("agent")
                uncertainty = e.get("uncertainty", 0.0)
                if agent:
                    acc[agent].append(float(uncertainty))
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
    except Exception:
        return {}
    
    return {k: sum(v) / len(v) for k, v in acc.items() if v}
