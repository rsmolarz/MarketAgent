import json
from pathlib import Path
from datetime import datetime, timezone

AGENTS_MANIFEST = Path("agent_schedule.json")
ALPHA_EVENTS = Path("alpha/reconciled.jsonl")
OUTPUT = Path("meta_supervisor/agent_proposals.json")

def load_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]

def run():
    existing_agents = set()
    if AGENTS_MANIFEST.exists():
        existing_agents = set(json.loads(AGENTS_MANIFEST.read_text()).keys())

    alpha = load_jsonl(ALPHA_EVENTS)

    markets = set(e.get("symbol") for e in alpha if e.get("symbol"))
    horizons = {"minutes", "hours", "daily"}

    proposals = []

    if "OptionsSkewFundingAgent" not in existing_agents:
        proposals.append({
            "agent_name": "OptionsSkewFundingAgent",
            "category": "Cross-market inefficiency",
            "markets": ["BTC", "ETH"],
            "horizon": "hours",
            "inefficiency_type": "Derivatives mispricing",
            "data_required": [
                "perp funding rates",
                "options IV skew",
                "open interest by strike"
            ],
            "why_missing": "Current agents treat funding and options independently",
            "expected_edge": "Funding extremes + skew inversion precede sharp mean reversion",
            "risk_profile": "Event-driven, convex",
            "test_plan": "Paper trade funding extremes when 25-delta skew flips sign",
            "confidence": 0.82
        })

    proposals.append({
        "agent_name": "ForcedSellerLiquidityAgent",
        "category": "Distressed asset flow",
        "markets": ["Crypto", "Rates", "Equities"],
        "horizon": "intraday",
        "inefficiency_type": "Liquidity shock",
        "data_required": [
            "order book depth",
            "liquidation feeds",
            "ETF flow data"
        ],
        "why_missing": "No agent currently models forced sellers explicitly",
        "expected_edge": "Forced selling creates short-lived price dislocations",
        "risk_profile": "High volatility, short duration",
        "test_plan": "Simulate entries after liquidation clusters",
        "confidence": 0.76
    })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
        "proposals": proposals
    }
    OUTPUT.write_text(json.dumps(out, indent=2))

    return proposals

if __name__ == "__main__":
    run()
