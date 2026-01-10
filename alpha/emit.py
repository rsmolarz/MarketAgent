import json
from pathlib import Path
from datetime import datetime, timezone

ALPHA = Path("alpha/events.jsonl")

def emit_alpha_signal(result: dict, agent_name: str):
    ALPHA.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
        "agent": agent_name,
        "symbol": result.get("symbol"),
        "direction": result.get("direction"),
        "prob_up": result.get("prob_up"),
        "confidence": result.get("confidence"),
        "score_final": result.get("ensemble_score_final"),
        "regime": result.get("regime"),
    }
    with open(ALPHA, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")
