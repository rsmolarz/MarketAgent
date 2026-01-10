import json
from pathlib import Path

POLICY = Path("meta_supervisor/policy/regime_policy.json")

DEFAULT_POLICY = {
  "caps": {
    "RISK_OFF": 0.20,
    "HIGH_VOL": 0.35,
    "MIXED": 0.60,
    "RISK_ON": 1.00
  },
  "unknown_cap": 0.50,
  "min_data_points": 20
}

def load_policy():
    if not POLICY.exists():
        POLICY.parent.mkdir(parents=True, exist_ok=True)
        POLICY.write_text(json.dumps(DEFAULT_POLICY, indent=2))
        return DEFAULT_POLICY
    return json.loads(POLICY.read_text())

def regime_cap(regime: str | None) -> float:
    p = load_policy()
    caps = p.get("caps", {})
    if not regime:
        return float(p.get("unknown_cap", 0.5))
    return float(caps.get(str(regime).upper(), p.get("unknown_cap", 0.5)))
