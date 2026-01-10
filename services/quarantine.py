import json
from pathlib import Path
from datetime import datetime, timezone

QPATH = Path("meta_supervisor/quarantine.json")


def _load():
    if not QPATH.exists():
        return {"agents": {}, "updated_at": None}
    try:
        return json.loads(QPATH.read_text())
    except Exception:
        return {"agents": {}, "updated_at": None}


def _save(doc):
    QPATH.parent.mkdir(parents=True, exist_ok=True)
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    QPATH.write_text(json.dumps(doc, indent=2))


def is_quarantined(agent_name: str) -> bool:
    doc = _load()
    a = doc["agents"].get(agent_name)
    if not a:
        return False
    return bool(a.get("active", False))


def quarantine(agent_name: str, reason: str):
    doc = _load()
    doc["agents"][agent_name] = {
        "active": True,
        "reason": reason,
        "since": datetime.now(timezone.utc).isoformat()
    }
    _save(doc)


def clear_quarantine(agent_name: str):
    doc = _load()
    if agent_name in doc["agents"]:
        doc["agents"][agent_name]["active"] = False
    _save(doc)


def quarantined_agents():
    doc = _load()
    return {k: v for k, v in doc.get("agents", {}).items() if v.get("active")}
