import json
from pathlib import Path
from datetime import datetime, timezone

CAPITAL_STATE = Path("meta_supervisor/state/capital.json")

DEFAULT = {
  "as_of": None,
  "nav_usd": 1_000_000,
  "risk_budget_pct": 0.02,
  "agent_risk_caps": {},
}

def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

def load_capital():
    if not CAPITAL_STATE.exists():
        CAPITAL_STATE.parent.mkdir(parents=True, exist_ok=True)
        CAPITAL_STATE.write_text(json.dumps(DEFAULT, indent=2))
        return DEFAULT
    try:
        return json.loads(CAPITAL_STATE.read_text())
    except Exception:
        return DEFAULT

def save_capital(s: dict):
    s["as_of"] = _now()
    CAPITAL_STATE.parent.mkdir(parents=True, exist_ok=True)
    CAPITAL_STATE.write_text(json.dumps(s, indent=2))

def capital_at_risk_by_agent(weights: dict, report: dict) -> dict:
    cap = load_capital()
    nav = float(cap.get("nav_usd", 0))
    risk_budget = nav * float(cap.get("risk_budget_pct", 0.02))

    fleet = report.get("fleet", {}) if report else {}
    portfolio_cvar_bps = float(fleet.get("portfolio_cvar95_bps", 0) or 0)
    if portfolio_cvar_bps <= 0:
        portfolio_cvar_usd = 0.01 * nav
    else:
        portfolio_cvar_usd = (portfolio_cvar_bps / 10_000.0) * nav

    caps = cap.get("agent_risk_caps", {}) or {}
    out = {}
    for a, w in (weights or {}).items():
        w = float(w)
        agent_cap = float(caps.get(a, 1.0))
        alloc_risk = risk_budget * w * agent_cap
        out[a] = {
            "weight": round(w, 6),
            "risk_budget_usd": round(alloc_risk, 2),
            "portfolio_cvar_usd": round(portfolio_cvar_usd, 2),
        }
    return out
