import os
import json
import time
import re
import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import logging

import requests

logger = logging.getLogger(__name__)


@dataclass
class CouncilResult:
    model: str
    ok: bool
    latency_ms: int
    raw_text: str
    parsed: Optional[Dict[str, Any]]
    error: Optional[str] = None


def _now_ms() -> int:
    return int(time.time() * 1000)


def _safe_json_extract(text: str) -> Optional[Dict[str, Any]]:
    """
    Tries to extract a JSON object from a model response.
    We ask models to return strict JSON, but this makes it resilient.
    """
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass

    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def _council_prompt(finding: Dict[str, Any]) -> str:
    """
    We force a strict schema so consensus is possible.
    """
    return f"""
You are an investment risk/market signal analyst.

Given this finding, output STRICT JSON ONLY matching the schema below. No markdown.

FINDING_JSON:
{json.dumps(finding, ensure_ascii=False)}

SCHEMA:
{{
  "verdict": "ACT" | "WATCH" | "IGNORE",
  "severity": "low" | "medium" | "high" | "critical",
  "confidence": number,  // 0..1
  "key_drivers": [string, ...],  // 3-6 items
  "what_to_verify": [string, ...],  // 2-5 items
  "time_horizon": "intraday" | "days" | "weeks" | "months",
  "positioning": {{
    "bias": "risk-on" | "risk-off" | "neutral",
    "suggested_actions": [string, ...]  // concrete steps, no trades required
  }},
  "one_paragraph_summary": string
}}

Rules:
- Be conservative: if uncertain, choose WATCH.
- confidence must reflect uncertainty.
- If missing data, put it into what_to_verify.
""".strip()


def call_openai(prompt: str, timeout_sec: int = 20) -> Tuple[bool, str, Optional[str]]:
    api_key = os.getenv("OPENAI_API_KEY", "") or os.getenv("AI_INTEGRATIONS_OPENAI_API_KEY", "")
    base_url = os.getenv("AI_INTEGRATIONS_OPENAI_BASE_URL", "https://api.openai.com/v1")
    
    if not api_key:
        return False, "", "OPENAI_API_KEY missing"

    url = f"{base_url}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": os.getenv("OPENAI_COUNCIL_MODEL", "gpt-4o"),
        "messages": [
            {"role": "system", "content": "Return strict JSON only."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=timeout_sec)
        r.raise_for_status()
        data = r.json()
        text = data["choices"][0]["message"]["content"]
        return True, text, None
    except Exception as e:
        logger.warning(f"OpenAI council call failed: {e}")
        return False, "", str(e)


def call_anthropic(prompt: str, timeout_sec: int = 20) -> Tuple[bool, str, Optional[str]]:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return False, "", "ANTHROPIC_API_KEY missing"

    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": os.getenv("ANTHROPIC_COUNCIL_MODEL", "claude-sonnet-4-20250514"),
        "max_tokens": 700,
        "temperature": 0.2,
        "messages": [{"role": "user", "content": prompt}],
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=timeout_sec)
        r.raise_for_status()
        data = r.json()
        text = "".join([blk.get("text", "") for blk in data.get("content", [])])
        return True, text, None
    except Exception as e:
        logger.warning(f"Anthropic council call failed: {e}")
        return False, "", str(e)


def call_gemini(prompt: str, timeout_sec: int = 20) -> Tuple[bool, str, Optional[str]]:
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return False, "", "GEMINI_API_KEY missing"

    model = os.getenv("GEMINI_COUNCIL_MODEL", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": "Return strict JSON only.\n\n" + prompt}]}],
        "generationConfig": {"temperature": 0.2},
    }

    try:
        r = requests.post(url, json=payload, timeout=timeout_sec)
        r.raise_for_status()
        data = r.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return True, text, None
    except Exception as e:
        logger.warning(f"Gemini council call failed: {e}")
        return False, "", str(e)


async def _call_async(name: str, fn, prompt: str, timeout_sec: int) -> CouncilResult:
    start = _now_ms()
    loop = asyncio.get_running_loop()
    ok, text, err = await loop.run_in_executor(None, fn, prompt, timeout_sec)
    latency = _now_ms() - start
    parsed = _safe_json_extract(text) if ok else None
    return CouncilResult(model=name, ok=ok, latency_ms=latency, raw_text=text, parsed=parsed, error=err)


def _normalize_vote(parsed: Dict[str, Any]) -> Tuple[str, float]:
    """
    Returns (verdict, confidence). Falls back safely.
    """
    verdict = (parsed.get("verdict") or "WATCH").upper()
    if verdict not in ("ACT", "WATCH", "IGNORE"):
        verdict = "WATCH"
    conf = parsed.get("confidence")
    try:
        conf = float(conf)
    except Exception:
        conf = 0.5
    conf = max(0.0, min(1.0, conf))
    return verdict, conf


def _consensus(results: List[CouncilResult], min_agree: int = 2) -> Dict[str, Any]:
    """
    Majority vote on verdict + confidence weighting.
    Also produces an uncertainty_spike boolean when disagreement is high.
    """
    usable = [r for r in results if r.ok and isinstance(r.parsed, dict)]
    if not usable:
        return {
            "ok": False,
            "reason": "No usable model outputs",
            "uncertainty_spike": True,
            "consensus": None,
        }

    votes = []
    for r in usable:
        verdict, conf = _normalize_vote(r.parsed)
        votes.append((verdict, conf, r.model))

    score = {"ACT": 0.0, "WATCH": 0.0, "IGNORE": 0.0}
    for v, conf, _ in votes:
        score[v] += conf

    counts = {"ACT": 0, "WATCH": 0, "IGNORE": 0}
    for v, _, _ in votes:
        counts[v] += 1

    sorted_by_count = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    top_verdict, top_count = sorted_by_count[0]

    if top_count < min_agree:
        uncertainty_spike = True
        top_verdict = max(score.items(), key=lambda kv: kv[1])[0]
    else:
        uncertainty_spike = (sorted_by_count[1][1] == top_count)

    best = max(votes, key=lambda t: t[1])
    best_model = best[2]
    best_parsed = next(r.parsed for r in usable if r.model == best_model)

    avg_conf = sum(conf for _, conf, _ in votes) / max(len(votes), 1)
    if uncertainty_spike:
        avg_conf *= 0.75
    avg_conf = round(avg_conf, 3)

    def _merge_list(field: str, limit: int) -> List[str]:
        out = []
        seen = set()
        for r in usable:
            items = r.parsed.get(field) or []
            if isinstance(items, list):
                for x in items:
                    if isinstance(x, str):
                        s = x.strip()
                        if s and s not in seen:
                            seen.add(s)
                            out.append(s)
            if len(out) >= limit:
                break
        return out[:limit]

    consensus_obj = {
        "verdict": top_verdict,
        "confidence": avg_conf,
        "uncertainty_spike": uncertainty_spike,
        "majority": counts,
        "weighted": {k: round(v, 3) for k, v in score.items()},
        "key_drivers": _merge_list("key_drivers", 6),
        "what_to_verify": _merge_list("what_to_verify", 5),
        "time_horizon": best_parsed.get("time_horizon", "days"),
        "positioning": best_parsed.get("positioning", {"bias": "neutral", "suggested_actions": []}),
        "one_paragraph_summary": best_parsed.get("one_paragraph_summary", ""),
    }

    return {"ok": True, "consensus": consensus_obj, "uncertainty_spike": uncertainty_spike}


async def analyze_with_council(finding: Dict[str, Any]) -> Dict[str, Any]:
    timeout_sec = int(os.getenv("LLM_COUNCIL_TIMEOUT_SEC", "20"))
    min_agree = int(os.getenv("LLM_COUNCIL_MIN_AGREE", "2"))
    prompt = _council_prompt(finding)

    tasks = [
        _call_async("openai", call_openai, prompt, timeout_sec),
        _call_async("claude", call_anthropic, prompt, timeout_sec),
        _call_async("gemini", call_gemini, prompt, timeout_sec),
    ]

    results = await asyncio.gather(*tasks)

    consensus = _consensus(results, min_agree=min_agree)

    return {
        "success": True,
        "models": [
            {
                "model": r.model,
                "ok": r.ok,
                "latency_ms": r.latency_ms,
                "error": r.error,
                "parsed": r.parsed,
                "raw_text": r.raw_text if not r.parsed else None,
            }
            for r in results
        ],
        "consensus": consensus.get("consensus"),
        "uncertainty_spike": consensus.get("uncertainty_spike", True),
        "ok": consensus.get("ok", False),
        "reason": consensus.get("reason"),
    }


def analyze_with_council_sync(finding: Dict[str, Any]) -> Dict[str, Any]:
    """Synchronous wrapper for analyze_with_council"""
    return asyncio.run(analyze_with_council(finding))


def llm_council_analyze_finding(finding) -> Dict[str, Any]:
    """
    Analyze a Finding model instance with the 3-LLM council.
    
    Returns:
        {
            "action": "ACT" | "WATCH" | "IGNORE",
            "confidence": float,
            "votes": {"openai": "...", "claude": "...", "gemini": "..."},
            "disagreement": bool,
            "full_consensus": {...}  # full consensus object for audit
        }
    """
    finding_dict = {
        "id": finding.id,
        "title": finding.title,
        "severity": finding.severity,
        "description": finding.description,
        "metadata": finding.finding_metadata,
        "symbol": finding.symbol,
        "market_type": finding.market_type,
        "confidence": finding.confidence,
        "agent_name": finding.agent_name,
    }
    
    try:
        result = analyze_with_council_sync(finding_dict)
        
        if not result.get("ok") or not result.get("consensus"):
            logger.warning(f"LLM Council failed for finding {finding.id}: {result.get('reason')}")
            return {
                "action": "WATCH",
                "confidence": 0.0,
                "votes": {},
                "disagreement": True,
                "full_consensus": None,
            }
        
        consensus = result["consensus"]
        verdict = consensus.get("verdict", "WATCH")
        action = "ACT" if verdict == "ACT" else ("IGNORE" if verdict == "IGNORE" else "WATCH")
        
        votes = {}
        for model_result in result.get("models", []):
            model_name = model_result.get("model", "unknown")
            if model_result.get("ok") and model_result.get("parsed"):
                votes[model_name] = model_result["parsed"].get("verdict", "WATCH")
            else:
                votes[model_name] = "ERROR"
        
        disagreement = result.get("uncertainty_spike", False)
        
        return {
            "action": action,
            "confidence": consensus.get("confidence", 0.5),
            "votes": votes,
            "disagreement": disagreement,
            "full_consensus": consensus,
        }
        
    except Exception as e:
        logger.error(f"LLM Council analysis failed for finding {finding.id}: {e}")
        return {
            "action": "WATCH",
            "confidence": 0.0,
            "votes": {},
            "disagreement": True,
            "full_consensus": None,
        }


def run_llm_council(finding) -> Dict[str, Any]:
    """
    Simple interface for LLM council analysis (matches user spec).
    
    Returns:
        {
            "consensus": "ACT" | "WATCH" | "IGNORE",
            "confidence": float,
            "agreement": float,
            "uncertainty": float,
            "votes": {"model": "vote"},
            "analyses": {"model": "text"}
        }
    """
    result = llm_council_analyze_finding(finding)
    
    votes = result.get("votes", {})
    act = sum(1 for v in votes.values() if v == "ACT")
    watch = sum(1 for v in votes.values() if v == "WATCH")
    ignore = sum(1 for v in votes.values() if v == "IGNORE")
    
    agreement = max(act, watch, ignore) / max(len(votes), 1)
    uncertainty = 1.0 - agreement
    
    analyses = {}
    full_consensus = result.get("full_consensus") or {}
    if full_consensus:
        analyses["summary"] = full_consensus.get("one_paragraph_summary", "")
    
    return {
        "consensus": result.get("action", "WATCH"),
        "confidence": result.get("confidence", 0.5),
        "agreement": agreement,
        "uncertainty": uncertainty,
        "votes": votes,
        "analyses": analyses
    }
