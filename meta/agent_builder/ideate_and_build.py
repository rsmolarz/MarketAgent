import json
from pathlib import Path
import importlib

from tools.llm_client import call_llm
from meta.agent_builder.builder import create_agent
from meta.agent_builder.eval_generator import generate_eval

IDEATION_PROMPT = Path("agents/prompts/agent_ideation.md").read_text()


def get_available_agents():
    mod = importlib.import_module("agents")
    return getattr(mod, "AVAILABLE_AGENTS", [])


def load_telemetry_summary():
    p = Path("telemetry/summary.json")
    if p.exists():
        return json.loads(p.read_text())
    return {}


def ideate_one():
    payload = {
        "available_agents": get_available_agents(),
        "telemetry_summary": load_telemetry_summary(),
        "constraints": {
            "offline_ci": True,
            "no_paid_datasets": True
        },
        "allowed_data_sources": [
            "existing internal clients",
            "RSS feeds",
            "public APIs"
        ],
        "required_finding_schema": ["title", "description", "severity", "confidence", "metadata", "symbol", "market_type"]
    }

    msgs = [
        {"role": "system", "content": IDEATION_PROMPT},
        {"role": "user", "content": json.dumps(payload)}
    ]
    out = call_llm(msgs, temperature=0.3, max_tokens=2200)
    return out


def main():
    idea = ideate_one()
    agent = idea["agent"]

    agent_name = agent["class_name"]
    create_agent(agent_name, {"description": agent["description"]})
    generate_eval(agent_name)

    Path("meta/reports").mkdir(parents=True, exist_ok=True)
    Path("meta/reports/ideation_last.json").write_text(json.dumps(idea, indent=2))

    print(f"Created agent scaffold + eval: {agent_name}")


if __name__ == "__main__":
    main()
