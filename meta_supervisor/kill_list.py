import json
from pathlib import Path

KILL = Path("meta_supervisor/policy/kill_list.json")

DEFAULT = {
  "agents": [],
  "strategy_classes": []
}

def load_kill_list():
    if not KILL.exists():
        KILL.parent.mkdir(parents=True, exist_ok=True)
        KILL.write_text(json.dumps(DEFAULT, indent=2))
        return DEFAULT
    return json.loads(KILL.read_text())

def is_killed(agent: str, strategy_class: str | None = None) -> bool:
    k = load_kill_list()
    if agent in (k.get("agents") or []):
        return True
    if strategy_class and strategy_class in (k.get("strategy_classes") or []):
        return True
    return False
