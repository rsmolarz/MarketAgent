import json
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

LOG_PATH = Path("telemetry/events.jsonl")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_run_id() -> str:
    return str(uuid.uuid4())


def log_event(
    agent: str,
    run_id: str,
    latency_ms: int,
    cost_usd: Optional[float] = None,
    tokens_in: Optional[int] = None,
    tokens_out: Optional[int] = None,
    error: Optional[str] = None,
    reward: Optional[float] = None,
):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    event = {
        "ts": _now_iso(),
        "agent": agent,
        "run_id": run_id,
        "latency_ms": latency_ms,
        "cost_usd": cost_usd,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "error": error,
        "reward": reward,
    }

    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")
