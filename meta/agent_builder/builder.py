import re
from pathlib import Path


AGENT_TEMPLATE = '''"""
{description}
"""
from typing import Any, Dict, List
from agents.base_agent import BaseAgent


class {class_name}(BaseAgent):
    """
    {description}
    """
    
    def __init__(self):
        super().__init__("{class_name}")
    
    def plan(self) -> Dict[str, Any]:
        """Plan the analysis strategy."""
        return {{
            "steps": ["fetch_data", "analyze", "generate_findings"]
        }}
    
    def act(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute the analysis and return findings."""
        return self.analyze()
    
    def analyze(self) -> List[Dict[str, Any]]:
        """
        Main analysis method. Returns list of findings.
        
        Each finding must have:
        - title (str)
        - description (str)
        - severity (low|medium|high)
        - confidence (0..1)
        - metadata (dict)
        - symbol (optional)
        - market_type (optional)
        """
        findings = []
        
        # TODO: Implement detection logic
        
        return findings
    
    def reflect(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Reflect on the analysis results."""
        return {{
            "finding_count": len(results),
            "high_severity_count": sum(1 for f in results if f.get("severity") == "high")
        }}
'''


def to_snake_case(name: str) -> str:
    """Convert CamelCase to snake_case."""
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def create_agent(class_name: str, config: dict) -> Path:
    """
    Create a new agent from template.
    
    Args:
        class_name: The agent class name (e.g., "MyNewAgent")
        config: Configuration dict with at least "description"
    
    Returns:
        Path to the created agent file
    """
    if not class_name.endswith("Agent"):
        class_name = f"{class_name}Agent"
    
    module_name = to_snake_case(class_name)
    description = config.get("description", f"Auto-generated {class_name}")
    
    agent_code = AGENT_TEMPLATE.format(
        class_name=class_name,
        description=description
    )
    
    agents_dir = Path("agents")
    agents_dir.mkdir(exist_ok=True)
    
    agent_file = agents_dir / f"{module_name}.py"
    agent_file.write_text(agent_code)
    
    _update_agents_init(class_name, module_name)
    
    return agent_file


def _update_agents_init(class_name: str, module_name: str):
    """Update agents/__init__.py to include the new agent."""
    init_file = Path("agents/__init__.py")
    
    if not init_file.exists():
        return
    
    content = init_file.read_text()
    
    import_line = f"from agents.{module_name} import {class_name}"
    if import_line not in content:
        lines = content.split('\n')
        insert_idx = 0
        for i, line in enumerate(lines):
            if line.startswith('from agents.'):
                insert_idx = i + 1
        
        lines.insert(insert_idx, import_line)
        content = '\n'.join(lines)
    
    if 'AVAILABLE_AGENTS' in content:
        if f'"{class_name}"' not in content:
            content = re.sub(
                r'(AVAILABLE_AGENTS\s*=\s*\[)',
                f'\\1\n    "{class_name}",',
                content
            )
    
    init_file.write_text(content)
