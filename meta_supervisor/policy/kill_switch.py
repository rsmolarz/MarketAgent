import json
from pathlib import Path

from services.quarantine import is_quarantined

KILL = Path("meta_supervisor/state/kill_switch.json")


def _load():
    if not KILL.exists():
        return {"disabled_agents": [], "disabled_strategies": []}
    try:
        return json.loads(KILL.read_text())
    except Exception:
        return {"disabled_agents": [], "disabled_strategies": []}


def _save(data):
    KILL.parent.mkdir(parents=True, exist_ok=True)
    KILL.write_text(json.dumps(data, indent=2))


def agent_disabled(agent: str) -> bool:
    if is_quarantined(agent):
        return True
    s = _load()
    return agent in (s.get("disabled_agents") or [])

def strategy_disabled(strategy_class: str) -> bool:
    s = _load()
    return strategy_class in (s.get("disabled_strategies") or [])

def disable_agents(agents: list, reason: str = ""):
    s = _load()
    cur = set(s.get("disabled_agents") or [])
    for a in agents:
        cur.add(a)
    s["disabled_agents"] = sorted(cur)
    s["last_reason"] = reason
    _save(s)

def disable_strategies(strategies: list, reason: str = ""):
    s = _load()
    cur = set(s.get("disabled_strategies") or [])
    for st in strategies:
        cur.add(st)
    s["disabled_strategies"] = sorted(cur)
    s["last_reason"] = reason
    _save(s)

def enable_agent(agent: str):
    s = _load()
    disabled = set(s.get("disabled_agents") or [])
    disabled.discard(agent)
    s["disabled_agents"] = sorted(disabled)
    _save(s)

def get_kill_switch_state():
    return _load()
