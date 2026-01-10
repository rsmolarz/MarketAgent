import json
from pathlib import Path
from meta_supervisor.lineage import register_child

AGENTS_DIR = Path("agents")
MANIFEST = Path("meta_supervisor/manifests/agents.json")

def _snake(x: str) -> str:
    return x.lower().replace(" ", "_").replace("-", "_")

def generate_agent_scaffold(proposal: dict):
    name = _snake(proposal["name"])
    agent_dir = AGENTS_DIR / name
    prompt_dir = agent_dir / "prompts"
    eval_dir = agent_dir / "eval"

    prompt_dir.mkdir(parents=True, exist_ok=True)
    eval_dir.mkdir(parents=True, exist_ok=True)

    (agent_dir / "agent.py").write_text(f'''
from agents.base import BaseAgent

class {proposal["name"].replace(" ", "")}Agent(BaseAgent):
    NAME = "{proposal["name"]}"
    STRATEGY_CLASS = "{proposal.get("strategy_class","unknown")}"

    def generate_signal(self, market_state: dict) -> dict:
        """
        TODO: Implement logic
        """
        return {{
            "symbol": None,
            "direction": None,
            "confidence": 0.0
        }}
'''.strip() + "\n")

    (prompt_dir / "main.txt").write_text(
        proposal.get("prompt", "Describe the market inefficiency you are targeting.")
    )

    (eval_dir / "test_agent.py").write_text(f'''
def test_{name}_basic():
    assert True
'''.strip() + "\n")

    manifest = {"agents": []}
    if MANIFEST.exists():
        manifest = json.loads(MANIFEST.read_text())

    if name not in manifest["agents"]:
        manifest["agents"].append(name)

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2))

    parent_agent = proposal.get("parent_agent") or proposal.get("derived_from") or "unknown"
    register_child(
        child=name,
        parent=parent_agent,
        reason=proposal.get("thesis", ""),
        proposal_id=proposal.get("id") or proposal.get("name")
    )

    return {
        "agent_name": name,
        "paths": [
            str(agent_dir),
            str(prompt_dir),
            str(eval_dir),
            str(MANIFEST),
        ]
    }
