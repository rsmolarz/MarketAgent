import json
import os
from pathlib import Path
from openai import OpenAI

REPORT = Path("meta_supervisor/reports/meta_report.json")
OUT = Path("meta_supervisor/agent_proposals_regime.json")

def _load():
    if not REPORT.exists():
        return {}
    return json.loads(REPORT.read_text())

def main():
    report = _load()
    if not report:
        return {}

    payload = {
        "fleet": report.get("fleet", {}),
        "strategy_cvar": report.get("strategy_cvar", {}),
        "agents": report.get("agents", {}),
        "research": report.get("research", {}),
    }

    key = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
    model = os.environ.get("AGENT_GEN_MODEL", "gpt-4.1-mini")
    client = OpenAI(api_key=key, base_url=base) if base else OpenAI(api_key=key)

    schema = {
        "proposals": [
            {
                "name": "string",
                "strategy_class": "string",
                "regime_trigger": "string",
                "thesis": "string",
                "data_sources": ["string"],
                "signals": ["string"],
                "eval_plan": {"offline": ["string"], "live_shadow": ["string"]},
                "risk_controls": ["string"],
                "expected_edge": "string"
            }
        ]
    }

    prompt = (
        "You design new agents for a market-inefficiency platform.\n"
        "Given the current report JSON, propose 3-8 new agents that fit gaps: trades, inefficiencies, distressed assets.\n"
        "Make them implementable in this codebase.\n"
        "Output JSON matching this schema exactly.\n\n"
        f"SCHEMA:\n{json.dumps(schema, indent=2)}\n\n"
        f"REPORT:\n{json.dumps(payload, indent=2)}"
    )

    resp = client.chat.completions.create(
        model=model,
        messages=[{"role":"system","content":"Output strict JSON only."},
                  {"role":"user","content":prompt}],
        temperature=0.2,
        max_tokens=1800,
        response_format={"type":"json_object"},
    )

    out = json.loads(resp.choices[0].message.content)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2))
    return out

if __name__ == "__main__":
    main()
