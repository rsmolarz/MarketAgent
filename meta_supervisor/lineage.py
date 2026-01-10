import json
from pathlib import Path
from datetime import datetime, timezone

LINEAGE = Path("meta_supervisor/state/lineage.json")

def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

def _load():
    if not LINEAGE.exists():
        return {"agents": {}}
    try:
        return json.loads(LINEAGE.read_text())
    except Exception:
        return {"agents": {}}

def _save(data):
    LINEAGE.parent.mkdir(parents=True, exist_ok=True)
    LINEAGE.write_text(json.dumps(data, indent=2))

def register_child(child: str, parent: str, reason: str, proposal_id: str | None = None):
    d = _load()
    d["agents"].setdefault(child, {})
    d["agents"][child].update({
        "parent": parent,
        "reason": reason,
        "proposal_id": proposal_id,
        "created_at": d["agents"][child].get("created_at") or _now()
    })
    _save(d)

def get_lineage():
    return _load()
