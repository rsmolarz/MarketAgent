import json
from pathlib import Path
from meta_supervisor.kill_list import load_kill_list

KILL = Path("meta_supervisor/policy/kill_list.json")

def apply_auto_kills(report: dict):
    k = load_kill_list()
    agents = report.get("agents", {}) or {}

    to_kill = [a for a, s in agents.items() if s.get("decision") in ("KILL", "RETIRE")]
    changed = False
    for a in to_kill:
        if a not in k["agents"]:
            k["agents"].append(a)
            changed = True

    if changed:
        KILL.parent.mkdir(parents=True, exist_ok=True)
        KILL.write_text(json.dumps(k, indent=2))
    return {"killed": to_kill, "changed": changed}
