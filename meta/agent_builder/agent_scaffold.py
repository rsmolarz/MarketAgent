from pathlib import Path
from textwrap import dedent

AGENTS_DIR = Path("agents")
AGENTS_DIR.mkdir(exist_ok=True)

AGENT_TEMPLATE = """\
from agents.base import BaseAgent

class {class_name}(BaseAgent):
    \"""
    {description}
    \"""

    name = "{class_name}"

    def analyze(self, data):
        return []
"""

def create_agent(class_name: str, spec: dict) -> Path:
    description = spec.get("description", "").strip() or "Auto-generated agent."

    file_name = f"{class_name}.py"
    path = AGENTS_DIR / file_name

    if path.exists():
        print(f">>> Agent already exists, skipping: {path}")
        return path

    code = AGENT_TEMPLATE.format(
        class_name=class_name,
        description=description,
    )

    path.write_text(dedent(code))
    print(f">>> Created agent file: {path}")
    return path
