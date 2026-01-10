from __future__ import annotations
from pathlib import Path
import json
from typing import Any, Dict

OUT_DIR = Path("backtest_results")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def write_result(agent_name: str, payload: Dict[str, Any]) -> Path:
    p = OUT_DIR / f"{agent_name}.json"
    p.write_text(json.dumps(payload, indent=2, default=str))
    return p

def load_result(agent_name: str) -> Dict[str, Any]:
    p = OUT_DIR / f"{agent_name}.json"
    if p.exists():
        return json.loads(p.read_text())
    return {}
