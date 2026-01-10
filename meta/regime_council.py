"""
LLM Regime Council

Multi-model regime assessment with:
1. Structured regime probabilities from each model
2. Confidence-weighted ensemble
3. Disagreement detection and uncertainty spikes

Key rules:
- Council output modulates SOFT behaviors (email priority, investigation depth)
- Deterministic risk layer (drawdown governor, hard stops) remains math-only
"""
import json
import math
import os
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from datetime import datetime

from tools.llm_providers import GPTProvider, ClaudeProvider, GeminiProvider, LLMProviderError

REGIMES = [
    "risk_on",
    "risk_off",
    "inflation_shock",
    "growth_slowdown",
    "liquidity_crunch",
    "geopolitical_shock",
    "rates_vol_spike",
]

SYSTEM_PROMPT = """You are a macro/regime analyst.
Return ONLY valid JSON matching the required schema. No markdown, no extra text.

Rules:
- regime_probs must include exactly the regimes given and sum to 1.0 (±0.01).
- confidence is your meta-confidence in this assessment (0.0-1.0).
- keep key_evidence to 3-7 bullets, concise.
"""

USER_TEMPLATE = """As-of UTC: {asof_utc}

Inputs (recent signals):
{signals}

Required regimes:
{regimes}

Return JSON:
{schema}
"""

SCHEMA_EXAMPLE = {
    "asof_utc": "YYYY-MM-DDTHH:MM:SSZ",
    "regime_probs": {k: 0.0 for k in REGIMES},
    "top_regime": "risk_off",
    "confidence": 0.5,
    "time_horizon_days": 10,
    "key_evidence": ["..."],
    "risk_flags": ["..."],
    "recommended_posture": {
        "exposure_multiplier": 1.0,
        "hedge_bias": "neutral",
        "notes": "..."
    }
}

CALIBRATION_PATH = os.path.join(os.path.dirname(__file__), "..", "eval", "regime_calibration.json")


@dataclass
class ModelVote:
    model: str
    raw_text: str
    parsed: Optional[Dict[str, Any]]
    error: Optional[str]


def _safe_json_parse(s: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(s)
    except Exception:
        start = s.find("{")
        end = s.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(s[start:end+1])
            except Exception:
                return None
        return None


def _normalize_probs(p: Dict[str, float]) -> Dict[str, float]:
    for r in REGIMES:
        p.setdefault(r, 0.0)
    p2 = {r: float(max(0.0, min(1.0, p[r]))) for r in REGIMES}
    s = sum(p2.values())
    if s <= 1e-9:
        u = 1.0 / len(REGIMES)
        return {r: u for r in REGIMES}
    return {r: p2[r] / s for r in REGIMES}


def entropy(probs: Dict[str, float]) -> float:
    e = 0.0
    for r in REGIMES:
        p = max(1e-12, float(probs.get(r, 0.0)))
        e -= p * math.log(p)
    return e


def mean_variance_across_models(model_probs: List[Dict[str, float]]) -> float:
    if not model_probs:
        return 0.0
    var_sum = 0.0
    for r in REGIMES:
        vals = [mp.get(r, 0.0) for mp in model_probs]
        m = sum(vals) / len(vals)
        var = sum((v - m) ** 2 for v in vals) / len(vals)
        var_sum += var
    return var_sum / len(REGIMES)


def load_calibration() -> Dict[str, float]:
    """Load learned reliability weights from calibration file."""
    if os.path.exists(CALIBRATION_PATH):
        try:
            with open(CALIBRATION_PATH) as f:
                data = json.load(f)
            return {m: data.get(m, {}).get("reliability", 1.0) for m in ["gpt", "claude", "gemini"]}
        except Exception:
            pass
    return {"gpt": 1.0, "claude": 1.0, "gemini": 1.0}


def save_calibration(calibration: Dict[str, Dict[str, float]]):
    """Save calibration data."""
    os.makedirs(os.path.dirname(CALIBRATION_PATH), exist_ok=True)
    with open(CALIBRATION_PATH, "w") as f:
        json.dump(calibration, f, indent=2)


def update_brier_score(model: str, predicted_prob: float, actual: int, alpha: float = 0.1):
    """
    Update EMA of Brier score for a model.
    actual: 1 if prediction was correct, 0 otherwise
    """
    calibration = {}
    if os.path.exists(CALIBRATION_PATH):
        try:
            with open(CALIBRATION_PATH) as f:
                calibration = json.load(f)
        except Exception:
            pass
    
    brier = (predicted_prob - actual) ** 2
    
    if model not in calibration:
        calibration[model] = {"ema_brier": brier, "reliability": 1.0 - brier}
    else:
        old_brier = calibration[model].get("ema_brier", 0.25)
        new_brier = alpha * brier + (1 - alpha) * old_brier
        calibration[model]["ema_brier"] = new_brier
        calibration[model]["reliability"] = max(0.1, 1.0 - new_brier)
    
    save_calibration(calibration)


class RegimeCouncil:
    """
    Multi-LLM regime assessment council.
    
    Calls GPT, Claude, and Gemini, aggregates their regime assessments
    with confidence weighting, and detects disagreement spikes.
    """
    
    def __init__(
        self,
        reliability_weights: Optional[Dict[str, float]] = None,
        gpt_model: str = "gpt-4o-mini",
        claude_model: str = "claude-sonnet-4-20250514",
        gemini_model: str = "gemini-2.0-flash",
    ):
        self.providers = {
            "gpt": GPTProvider(model=gpt_model),
            "claude": ClaudeProvider(model=claude_model),
            "gemini": GeminiProvider(model=gemini_model),
        }
        self.reliability = reliability_weights or load_calibration()

    def run(self, asof_utc: str, signals: str) -> Dict[str, Any]:
        """
        Run the regime council.
        
        Args:
            asof_utc: Timestamp for the assessment
            signals: Recent market signals/findings to analyze
            
        Returns:
            Dict with ensemble probabilities, weights, disagreement metrics
        """
        user = USER_TEMPLATE.format(
            asof_utc=asof_utc,
            signals=signals,
            regimes=", ".join(REGIMES),
            schema=json.dumps(SCHEMA_EXAMPLE, indent=2),
        )

        votes: List[ModelVote] = []
        for name, prov in self.providers.items():
            try:
                raw = prov.call(SYSTEM_PROMPT, user)
                parsed = _safe_json_parse(raw)
                votes.append(ModelVote(model=name, raw_text=raw, parsed=parsed, error=None))
            except Exception as e:
                votes.append(ModelVote(model=name, raw_text="", parsed=None, error=str(e)))

        valid = [v for v in votes if isinstance(v.parsed, dict)]
        if not valid:
            return {
                "ok": False,
                "error": "No valid council responses",
                "votes": [{"model": v.model, "error": v.error} for v in votes],
            }

        model_probs: Dict[str, Dict[str, float]] = {}
        model_conf: Dict[str, float] = {}
        top_regimes: Dict[str, str] = {}
        
        for v in valid:
            p = v.parsed.get("regime_probs", {})
            p = _normalize_probs(p if isinstance(p, dict) else {})
            model_probs[v.model] = p
            c = float(v.parsed.get("confidence", 0.5))
            model_conf[v.model] = max(0.0, min(1.0, c))
            top_regimes[v.model] = str(v.parsed.get("top_regime", "")).strip()

        weights: Dict[str, float] = {}
        for m in model_probs.keys():
            weights[m] = float(self.reliability.get(m, 1.0)) * float(model_conf.get(m, 0.5))

        wsum = sum(weights.values()) or 1.0
        weights = {m: w / wsum for m, w in weights.items()}

        ensemble = {r: 0.0 for r in REGIMES}
        for m, p in model_probs.items():
            for r in REGIMES:
                ensemble[r] += weights[m] * p[r]
        ensemble = _normalize_probs(ensemble)

        unique_tops = {top_regimes[m] for m in top_regimes if top_regimes[m]}
        vote_split = len(unique_tops) if unique_tops else 0
        prob_var = mean_variance_across_models(list(model_probs.values()))
        ent = entropy(ensemble)

        uncertainty_spike = (vote_split >= 2) or (prob_var > 0.02) or (ent > 1.4)

        top_regime = max(ensemble.items(), key=lambda kv: kv[1])[0]
        
        evidence = []
        risk_flags = []
        postures = []
        
        for v in valid:
            ev = v.parsed.get("key_evidence", [])
            if isinstance(ev, list):
                for item in ev[:2]:
                    s = str(item).strip()
                    if s:
                        evidence.append(f"{v.model}: {s}")
            
            rf = v.parsed.get("risk_flags", [])
            if isinstance(rf, list):
                risk_flags.extend(rf)
            
            pos = v.parsed.get("recommended_posture", {})
            if isinstance(pos, dict):
                postures.append({
                    "model": v.model,
                    "exposure_multiplier": pos.get("exposure_multiplier", 1.0),
                    "hedge_bias": pos.get("hedge_bias", "neutral"),
                })

        avg_exposure = sum(p.get("exposure_multiplier", 1.0) for p in postures) / len(postures) if postures else 1.0

        result = {
            "ok": True,
            "asof_utc": asof_utc,
            "ensemble": {
                "regime_probs": {k: round(v, 4) for k, v in ensemble.items()},
                "top_regime": top_regime,
                "entropy": round(ent, 4),
                "confidence": round(float(max(ensemble.values())), 4),
            },
            "weights_used": {k: round(v, 4) for k, v in weights.items()},
            "disagreement": {
                "vote_split": vote_split,
                "prob_var": round(prob_var, 6),
                "uncertainty_spike": uncertainty_spike,
                "unique_top_regimes": sorted(list(unique_tops)),
            },
            "recommended_exposure": round(avg_exposure, 2),
            "risk_flags": list(set(risk_flags))[:10],
            "evidence": evidence[:12],
            "votes": [
                {
                    "model": v.model,
                    "error": v.error,
                    "parsed_ok": isinstance(v.parsed, dict),
                    "top_regime": (v.parsed or {}).get("top_regime"),
                    "confidence": (v.parsed or {}).get("confidence"),
                }
                for v in votes
            ],
        }
        return result


def build_signals_from_findings(findings: List[Dict], market_data: Dict = None) -> str:
    """
    Build signals string from recent findings and market data.
    """
    lines = []
    
    if market_data:
        if "vix" in market_data:
            lines.append(f"- VIX: {market_data['vix']}")
        if "spy_return" in market_data:
            lines.append(f"- SPY 1d return: {market_data['spy_return']:.2%}")
        if "rates_10y" in market_data:
            lines.append(f"- 10Y yield: {market_data['rates_10y']:.2%}")
    
    agent_summary = {}
    for f in findings[:50]:
        agent = f.get("agent") or f.get("agent_name", "Unknown")
        if agent not in agent_summary:
            agent_summary[agent] = {"count": 0, "severities": []}
        agent_summary[agent]["count"] += 1
        agent_summary[agent]["severities"].append(f.get("severity", "low"))
    
    for agent, data in agent_summary.items():
        high_sev = sum(1 for s in data["severities"] if s in ["high", "critical"])
        lines.append(f"- {agent}: {data['count']} findings ({high_sev} high/critical)")
    
    for f in findings[:5]:
        title = f.get("title", "")[:80]
        sev = f.get("severity", "low")
        lines.append(f"- [{sev}] {title}")
    
    return "\n".join(lines) if lines else "- No recent signals available"
