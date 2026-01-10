import json
import os
from pathlib import Path
from datetime import datetime, timezone

from openai import OpenAI

REPORT = Path("meta_supervisor/reports/meta_report.json")
HIST = Path("meta_supervisor/state/allocation_history.jsonl")
OUT = Path("meta_supervisor/reports/weekly_change_summary.json")

def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def _load_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]

def build_weekly_context(report: dict, hist: list[dict]) -> dict:
    last = hist[-14:]
    if len(last) < 3:
        return {"note": "insufficient_history", "snapshots": last, "report": report}

    w0 = last[0].get("weights", {}) or {}
    w1 = last[-1].get("weights", {}) or {}
    agents = set(w0.keys()) | set(w1.keys())
    deltas = {a: round(float(w1.get(a, 0)) - float(w0.get(a, 0)), 4) for a in agents}
    top_moves = sorted(deltas.items(), key=lambda kv: abs(kv[1]), reverse=True)[:10]

    pnl0 = last[0].get("portfolio_pnl_bps")
    pnl1 = last[-1].get("portfolio_pnl_bps")

    return {
        "generated_at": report.get("meta", {}).get("generated_at"),
        "severity": report.get("meta", {}).get("severity"),
        "portfolio": {
            "pnl_start_bps": pnl0,
            "pnl_end_bps": pnl1,
        },
        "top_allocation_moves": top_moves,
        "promote": [k for k, v in (report.get("agents") or {}).items() if v.get("decision") == "PROMOTE"],
        "kill_retire": [k for k, v in (report.get("agents") or {}).items() if v.get("decision") in ("KILL", "RETIRE")],
        "regime_multipliers": report.get("meta", {}).get("regime_multipliers", {}),
        "allocation_method": (report.get("allocation") or {}).get("method"),
    }

def summarize_with_llm(context: dict) -> dict:
    api_key = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
    model = os.environ.get("WEEKLY_SUMMARY_MODEL", "gpt-4.1-mini")

    if not api_key:
        return {"ok": False, "error": "missing_api_key"}

    client = OpenAI(api_key=api_key, base_url=base_url)

    system = (
        "You are an institutional quant PM assistant. "
        "Write a weekly change summary for LPs. "
        "Be specific, short, and audit-friendly. No hype. "
        "Output strict JSON with keys: headline, bullets, risks, actions."
    )
    user = json.dumps({"context": context})

    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.2,
    )

    content = resp.choices[0].message.content
    try:
        j = json.loads(content)
        j["ok"] = True
        j["generated_at"] = _now()
        return j
    except Exception:
        return {"ok": False, "error": "non_json_response", "raw": content, "generated_at": _now()}

def main():
    report = json.loads(REPORT.read_text()) if REPORT.exists() else {}
    hist = _load_jsonl(HIST)

    context = build_weekly_context(report, hist)
    summary = summarize_with_llm(context)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"context": context, "summary": summary}, indent=2))
    return summary

if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
