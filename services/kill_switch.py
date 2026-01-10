import json
from pathlib import Path
from datetime import datetime, timezone

from meta_supervisor.agent_registry import AGENT_STRATEGY_CLASS

KILLED_AGENTS = Path("meta_supervisor/state/killed_agents.json")
KILLED_STRATEGIES = Path("meta_supervisor/state/killed_strategies.json")

def _load_list(p: Path):
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text())
    except Exception:
        return []

def _load_agent_dict(p: Path) -> dict:
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text())
        if isinstance(data, list):
            return {a.get("agent"): a for a in data if isinstance(a, dict) and a.get("agent")}
        return {}
    except Exception:
        return {}

def _save_agents(data: dict):
    KILLED_AGENTS.parent.mkdir(parents=True, exist_ok=True)
    items = [{"agent": k, **v} for k, v in data.items()]
    KILLED_AGENTS.write_text(json.dumps(items, indent=2))

def _save_strategies(strategies: set):
    KILLED_STRATEGIES.parent.mkdir(parents=True, exist_ok=True)
    KILLED_STRATEGIES.write_text(json.dumps(sorted(strategies), indent=2))

def is_agent_killed(agent_name: str) -> bool:
    data = _load_list(KILLED_AGENTS)
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return any(a.get("agent") == agent_name for a in data)
    return agent_name in set(data)

def is_strategy_killed(agent_name: str) -> bool:
    cls = AGENT_STRATEGY_CLASS.get(agent_name)
    if not cls:
        return False
    return cls in set(_load_list(KILLED_STRATEGIES))

def is_killed(agent_name: str) -> bool:
    return is_agent_killed(agent_name) or is_strategy_killed(agent_name)

def kill_agent(agent_name: str, reason: str = ""):
    """Add an agent to the kill list"""
    data = _load_agent_dict(KILLED_AGENTS)
    data[agent_name] = {
        "killed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "reason": reason,
    }
    _save_agents(data)

def revive_agent(agent_name: str) -> bool:
    """Remove an agent from the kill list"""
    data = _load_agent_dict(KILLED_AGENTS)
    if agent_name in data:
        del data[agent_name]
        _save_agents(data)
        return True
    return False

def get_killed_agents() -> list:
    """Get list of all killed agents with their info"""
    data = _load_agent_dict(KILLED_AGENTS)
    return [{"agent": k, **v} for k, v in data.items()]

def kill_strategy(strategy_class: str, reason: str = ""):
    """Add a strategy class to the kill list"""
    strategies = set(_load_list(KILLED_STRATEGIES))
    strategies.add(strategy_class)
    _save_strategies(strategies)

def revive_strategy(strategy_class: str) -> bool:
    """Remove a strategy class from the kill list"""
    strategies = set(_load_list(KILLED_STRATEGIES))
    if strategy_class in strategies:
        strategies.remove(strategy_class)
        _save_strategies(strategies)
        return True
    return False

def get_killed_strategies() -> list:
    """Get list of all killed strategy classes"""
    return sorted(_load_list(KILLED_STRATEGIES))
