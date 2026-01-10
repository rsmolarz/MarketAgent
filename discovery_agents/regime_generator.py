import json
from pathlib import Path
from datetime import datetime, timezone

ALPHA = Path("alpha/events.jsonl")
OUT = Path("meta_supervisor/agent_proposals_regime.json")

def load_jsonl(p: Path):
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]

def run(lookback: int = 300):
    events = load_jsonl(ALPHA)[-lookback:]
    regimes = [e.get("regime","MIXED") for e in events if e.get("regime")]
    if not regimes:
        regimes = ["MIXED"]

    dom = max(set(regimes), key=regimes.count)

    proposals = []
    if dom.upper().startswith("TREND"):
        proposals.append({
            "agent_name": "BreakoutContinuationAgent",
            "strategy_class": "trend_following",
            "edge_hypothesis": "Continuation after volatility compression + breakout confirmation",
            "markets": ["BTC","ETH"],
            "horizon": "hours",
            "data_required": ["intraday OHLCV", "ATR", "VWAP bands"],
            "test_plan": "Walk-forward on 3m/1h; require vol squeeze then close above VWAP+band",
            "confidence": 0.72
        })
    elif "MEAN" in dom.upper():
        proposals.append({
            "agent_name": "LiquidityMeanReversionAgent",
            "strategy_class": "mean_reversion",
            "edge_hypothesis": "Reversion after funding/OI extremes + value-area re-entry",
            "markets": ["BTC","ETH","SOL"],
            "horizon": "hours",
            "data_required": ["funding", "OI", "market profile levels"],
            "test_plan": "Enter when price returns to value after spike and funding in extreme percentile",
            "confidence": 0.74
        })
    else:
        proposals.append({
            "agent_name": "RegimeClassifierEnhancerAgent",
            "strategy_class": "meta_regime",
            "edge_hypothesis": "Improve regime detection to reduce cross-regime losses",
            "markets": ["crypto","equities","rates"],
            "horizon": "daily",
            "data_required": ["volatility", "correlations", "breadth", "rates stress"],
            "test_plan": "Compare new classifier vs current on failure_forensics windows",
            "confidence": 0.68
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
        "dominant_regime": dom,
        "proposals": proposals
    }, indent=2))

    return proposals

if __name__ == "__main__":
    run()
