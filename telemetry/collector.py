import json, time
from pathlib import Path
from datetime import datetime, timezone

EVENTS = Path("telemetry/events.jsonl")

def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

class RunTelemetry:
    def __init__(self, agent: str, run_id: str):
        self.agent = agent
        self.run_id = run_id
        self.t0 = time.time()
        self.tokens_in = 0
        self.tokens_out = 0
        self.cost_usd = 0.0
        self.errors = 0

    def add_llm_usage(self, tokens_in: int, tokens_out: int, cost_usd: float = 0.0):
        self.tokens_in += tokens_in
        self.tokens_out += tokens_out
        self.cost_usd += cost_usd

    def add_error(self):
        self.errors += 1

    def flush(self):
        EVENTS.parent.mkdir(parents=True, exist_ok=True)
        dt_ms = int((time.time() - self.t0) * 1000)
        record = {
            "ts": _now(),
            "agent": self.agent,
            "run_id": self.run_id,
            "latency_ms": dt_ms,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "cost_usd": round(self.cost_usd, 6),
            "errors": self.errors,
        }
        with open(EVENTS, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
