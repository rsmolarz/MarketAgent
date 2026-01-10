import json
from pathlib import Path

FLEET = Path("meta_supervisor/state/fleet.json")

def save_fleet(fleet: dict):
    FLEET.parent.mkdir(parents=True, exist_ok=True)
    FLEET.write_text(json.dumps(fleet, indent=2))

def get_current_regime() -> str | None:
    if not FLEET.exists():
        return None
    try:
        data = json.loads(FLEET.read_text())
        return data.get("current_regime")
    except Exception:
        return None
