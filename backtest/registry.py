from __future__ import annotations
from typing import Dict, Any, List
from pathlib import Path
import yaml

def load_manifest(path: str = "agents/manifest.yaml") -> Dict[str, Any]:
    p = Path(path)
    return yaml.safe_load(p.read_text())

def list_agents(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    return manifest.get("agents", [])

def import_agent_class(module_path: str, class_name: str):
    import importlib
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)
