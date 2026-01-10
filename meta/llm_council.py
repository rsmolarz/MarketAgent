import os
import math
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _softmax(xs: List[float]) -> List[float]:
    m = max(xs) if xs else 0
    ex = [math.exp(x - m) for x in xs]
    s = sum(ex) or 1.0
    return [e / s for e in ex]


def _normalize_vote(v: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "model": v.get("model", "unknown"),
        "uncertainty": _clamp(float(v.get("uncertainty", 0.0))),
        "label": v.get("label", "calm"),
        "confidence": _clamp(float(v.get("confidence", 0.5))),
        "meta": v.get("meta", {}),
    }


def _disagreement(votes: List[Dict[str, Any]]) -> float:
    if len(votes) <= 1:
        return 0.0
    u = [v["uncertainty"] for v in votes]
    mean = sum(u) / len(u)
    var = sum((x - mean) ** 2 for x in u) / (len(u) - 1)
    std = math.sqrt(var)
    return _clamp(std / 0.35)


def _aggregate_label(votes: List[Dict[str, Any]]) -> str:
    buckets = {"calm": 0.0, "risk_off": 0.0, "transition": 0.0, "shock": 0.0}
    for v in votes:
        lbl = v["label"] if v["label"] in buckets else "calm"
        buckets[lbl] += v["confidence"]
    return max(buckets.items(), key=lambda kv: kv[1])[0]


def _aggregate_uncertainty(votes: List[Dict[str, Any]]) -> float:
    wsum = sum(v["confidence"] for v in votes) or 1.0
    return sum(v["uncertainty"] * v["confidence"] for v in votes) / wsum


def _call_openai(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from openai import OpenAI
        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY")
        base_url = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
        if not api_key:
            return None
        client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
        
        prompt = f"""Analyze market uncertainty based on this data:
Regime: {payload.get('regime_state', 'unknown')}
Top findings: {len(payload.get('top_findings', []))} recent signals

Rate market uncertainty from 0 (calm) to 1 (extreme).
Label as: calm, risk_off, transition, or shock.
Confidence in your assessment: 0-1.

Respond in format: uncertainty=X.XX|label=LABEL|confidence=X.XX"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.3
        )
        
        text = response.choices[0].message.content or ""
        parts = dict(p.split("=") for p in text.strip().split("|") if "=" in p)
        
        return {
            "model": "gpt",
            "uncertainty": float(parts.get("uncertainty", 0.35)),
            "label": parts.get("label", "transition"),
            "confidence": float(parts.get("confidence", 0.65)),
        }
    except Exception as e:
        logger.warning(f"OpenAI council call failed: {e}")
        return None


def _call_anthropic(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        import anthropic
        client = anthropic.Anthropic()
        
        prompt = f"""Analyze market uncertainty based on this data:
Regime: {payload.get('regime_state', 'unknown')}
Top findings: {len(payload.get('top_findings', []))} recent signals

Rate market uncertainty from 0 (calm) to 1 (extreme).
Label as: calm, risk_off, transition, or shock.
Confidence in your assessment: 0-1.

Respond in format: uncertainty=X.XX|label=LABEL|confidence=X.XX"""
        
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}]
        )
        
        text = response.content[0].text if response.content else ""
        parts = dict(p.split("=") for p in text.strip().split("|") if "=" in p)
        
        return {
            "model": "claude",
            "uncertainty": float(parts.get("uncertainty", 0.40)),
            "label": parts.get("label", "transition"),
            "confidence": float(parts.get("confidence", 0.60)),
        }
    except Exception as e:
        logger.warning(f"Anthropic council call failed: {e}")
        return None


def _call_gemini(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        import google.generativeai as genai
        
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return None
            
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        prompt = f"""Analyze market uncertainty based on this data:
Regime: {payload.get('regime_state', 'unknown')}
Top findings: {len(payload.get('top_findings', []))} recent signals

Rate market uncertainty from 0 (calm) to 1 (extreme).
Label as: calm, risk_off, transition, or shock.
Confidence in your assessment: 0-1.

Respond in format: uncertainty=X.XX|label=LABEL|confidence=X.XX"""
        
        response = model.generate_content(prompt)
        text = response.text or ""
        parts = dict(p.split("=") for p in text.strip().split("|") if "=" in p)
        
        return {
            "model": "gemini",
            "uncertainty": float(parts.get("uncertainty", 0.30)),
            "label": parts.get("label", "risk_off"),
            "confidence": float(parts.get("confidence", 0.55)),
        }
    except Exception as e:
        logger.warning(f"Gemini council call failed: {e}")
        return None


def run_llm_council(payload: Dict[str, Any]) -> Dict[str, Any]:
    votes: List[Dict[str, Any]] = []

    if os.getenv("OPENAI_API_KEY") or os.getenv("AI_INTEGRATIONS_OPENAI_API_KEY"):
        result = _call_openai(payload)
        if result:
            votes.append(result)

    if os.getenv("ANTHROPIC_API_KEY"):
        result = _call_anthropic(payload)
        if result:
            votes.append(result)

    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        result = _call_gemini(payload)
        if result:
            votes.append(result)

    if not votes:
        votes.append({"model": "fallback", "uncertainty": 0.15, "label": "calm", "confidence": 0.40})

    votes = [_normalize_vote(v) for v in votes]
    disagreement = _disagreement(votes)
    score = _aggregate_uncertainty(votes)
    label = _aggregate_label(votes)

    spike = (score >= 0.65) or (disagreement >= 0.60)

    logger.info(f"LLM Council: score={score:.2f} label={label} spike={spike} disagree={disagreement:.2f} models={[v['model'] for v in votes]}")

    return {
        "score": float(score),
        "label": label,
        "spike": bool(spike),
        "disagreement": float(disagreement),
        "votes": votes,
    }
