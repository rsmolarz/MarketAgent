import json
from pathlib import Path
from datetime import datetime

LOG = Path("telemetry/uncertainty_events.jsonl")


def log_uncertainty(agent: str, finding_id: int, uncertainty: float):
    """
    Append uncertainty event to JSONL log for audit and allocator feed.
    """
    LOG.parent.mkdir(parents=True, exist_ok=True)
    
    event = {
        "ts": datetime.utcnow().isoformat(),
        "agent": agent,
        "finding_id": finding_id,
        "uncertainty": round(uncertainty, 4)
    }
    
    with open(LOG, "a") as f:
        f.write(json.dumps(event) + "\n")
