import json
import os
from pathlib import Path

REPORT = Path("meta_supervisor/reports/meta_report.json")
OUT_MD = Path("meta_supervisor/reports/ic_weekly.md")

def _load():
    if not REPORT.exists():
        return {}
    return json.loads(REPORT.read_text())

def build_prompt(report: dict) -> str:
    agents = report.get("agents", {})
    fleet = report.get("fleet", {})
    strategy_cvar = report.get("strategy_cvar", {})
    capital = report.get("capital", {})

    top = sorted(agents.items(), key=lambda kv: kv[1].get("pnl_sum_bps", 0), reverse=True)[:8]
    bottom = sorted(agents.items(), key=lambda kv: kv[1].get("pnl_sum_bps", 0))[:8]

    payload = {
        "fleet": fleet,
        "top_agents": [{ "agent": a, **s } for a, s in top],
        "bottom_agents": [{ "agent": a, **s } for a, s in bottom],
        "strategy_cvar": strategy_cvar,
        "capital": capital,
        "decisions": {
            "promote": [a for a, s in agents.items() if s.get("decision") == "PROMOTE"],
            "kill": [a for a, s in agents.items() if s.get("decision") in ("KILL", "RETIRE")],
        }
    }

    return (
        "You are the portfolio PM writing a weekly IC memo for a quant multi-agent trading system.\n"
        "Write a crisp memo with: Executive summary, performance, risk, what changed, decisions, and next-week plan.\n"
        "Be specific and cite metrics from the JSON.\n\n"
        f"JSON:\n{json.dumps(payload, indent=2)}"
    )

def generate_ic_memo_llm(report: dict) -> str:
    from openai import OpenAI

    key = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
    model = os.environ.get("IC_MEMO_MODEL", "gpt-4.1-mini")

    client = OpenAI(api_key=key, base_url=base) if base else OpenAI(api_key=key)
    prompt = build_prompt(report)

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Output markdown only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=1800,
    )
    return resp.choices[0].message.content

def main():
    report = _load()
    if not report:
        return None

    memo = generate_ic_memo_llm(report)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(memo, encoding="utf-8")
    return memo

if __name__ == "__main__":
    main()
