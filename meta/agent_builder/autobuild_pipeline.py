import json
import re
import subprocess
from pathlib import Path
import importlib
import yaml

from tools.llm_client import call_llm
from meta.agent_builder.agent_scaffold import create_agent
from meta.agent_builder.eval_generator import generate_eval

SANDBOX_SELF_MODIFIER = Path("meta/sandbox_self_modifier.py")

IDEATION_PROMPT_PATH = Path("agents/prompts/agent_ideation.md")
MANIFEST_PATH = Path("agents/manifest.yaml")


def git(cmd: str) -> str:
    try:
        return subprocess.check_output(["bash", "-lc", cmd], text=True, stderr=subprocess.DEVNULL).strip()
    except subprocess.CalledProcessError:
        return ""


def snake_case(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def class_name_from_module(module_slug: str) -> str:
    return "".join(x.capitalize() for x in module_slug.split("_"))


def get_available_agents():
    mod = importlib.import_module("agents")
    return getattr(mod, "AVAILABLE_AGENTS", [])


def load_telemetry_summary():
    p = Path("telemetry/summary.json")
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return {}
    return {}


def ideate_one() -> dict:
    if not IDEATION_PROMPT_PATH.exists():
        raise RuntimeError(f"Missing ideation prompt: {IDEATION_PROMPT_PATH}")

    prompt = IDEATION_PROMPT_PATH.read_text()

    payload = {
        "available_agents": get_available_agents(),
        "telemetry_summary": load_telemetry_summary(),
        "constraints": {
            "offline_ci": True,
            "no_paid_datasets": True,
            "analysis_only": True
        },
        "allowed_data_sources": [
            "existing internal clients",
            "RSS feeds",
            "public APIs",
            "file fixtures for CI"
        ],
        "required_finding_schema": [
            "title", "description", "severity", "confidence", "metadata", "symbol", "market_type"
        ]
    }

    msgs = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": json.dumps(payload)}
    ]
    out = call_llm(msgs, temperature=0.3, max_tokens=2400)
    if not isinstance(out, dict) or "agent" not in out or "eval" not in out:
        raise RuntimeError("Ideation model returned invalid JSON (missing agent/eval).")
    return out


def ensure_manifest():
    if not MANIFEST_PATH.exists():
        raise RuntimeError("agents/manifest.yaml not found. Required for sandbox modifier.")
    manifest = yaml.safe_load(MANIFEST_PATH.read_text())
    if "agents" not in manifest or not isinstance(manifest["agents"], list):
        raise RuntimeError("agents/manifest.yaml is missing 'agents' list.")
    return manifest


def add_agent_to_manifest(manifest: dict, agent_class_name: str, module_slug: str, eval_suite_path: str):
    for a in manifest["agents"]:
        if a.get("name") == agent_class_name:
            return

    manifest["agents"].append({
        "name": agent_class_name,
        "module": f"agents.{module_slug}",
        "callable": "run",
        "eval_suite": eval_suite_path,
        "eval_adapter": None,
        "sandbox_editable": True,
        "execution_sensitive": False
    })


def write_eval_suite(agent_name: str, eval_spec: dict) -> str:
    """
    Write an eval suite based on ideation output.
    If ideation doesn't provide structured cases, fall back to generator.
    """
    Path("eval/suites").mkdir(parents=True, exist_ok=True)
    suite_path = Path("eval/suites") / f"{agent_name}.jsonl"

    cases = eval_spec.get("cases")
    if isinstance(cases, list) and cases:
        lines = []
        for c in cases:
            lines.append(json.dumps(c))
        suite_path.write_text("\n".join(lines) + "\n")
        return str(suite_path)

    p = generate_eval(agent_name)
    return str(p)


def run_sandbox_self_modifier():
    if not SANDBOX_SELF_MODIFIER.exists():
        raise RuntimeError(f"Sandbox self-modifier not found at {SANDBOX_SELF_MODIFIER}")

    cmd = f"python {SANDBOX_SELF_MODIFIER}"
    out = subprocess.check_output(["bash", "-lc", cmd], text=True)
    return out


def main(n_agents: int = 3):
    manifest = ensure_manifest()

    Path("meta/reports").mkdir(parents=True, exist_ok=True)

    built = []
    for i in range(n_agents):
        idea = ideate_one()
        agent = idea["agent"]
        eval_spec = idea["eval"]

        class_name = agent["class_name"]
        module_slug = agent.get("module_slug") or snake_case(class_name)

        create_agent(class_name, {"description": agent.get("description", "")})

        suite_path = write_eval_suite(class_name, eval_spec)

        add_agent_to_manifest(manifest, class_name, module_slug, suite_path)

        Path(f"meta/reports/ideation_{class_name}.json").write_text(json.dumps(idea, indent=2))

        built.append(class_name)

        git("git add agents/ eval/suites/ meta/reports/ agents/manifest.yaml")
        git(f'git commit -m "AgentBuilder: scaffold {class_name} + eval suite"')

    MANIFEST_PATH.write_text(yaml.safe_dump(manifest, sort_keys=False))
    git("git add agents/manifest.yaml")
    git('git commit -m "AgentBuilder: register new agents in manifest"')

    sandbox_log = run_sandbox_self_modifier()
    Path("meta/reports/sandbox_self_modifier_last.log").write_text(sandbox_log)

    print(f"Built agents: {built}")
    print("Sandbox improvement attempted; check git log and meta/reports/ for details.")


if __name__ == "__main__":
    main(3)
