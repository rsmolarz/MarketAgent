import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.llm_client import call_llm

def tune_prompt(prompt_path: str, failure_summary: dict, policy: dict) -> str:
    prompt_text = Path(prompt_path).read_text()

    tuner_path = Path("agents/prompts/prompt_tuner.md")
    guidelines_path = Path("agents/prompts/agent_guidelines.md")
    
    system = tuner_path.read_text() if tuner_path.exists() else \
        "You are the Prompt-Tuning Agent. Output STRICT JSON only: {\"updated_prompt\":\"...\"}"
    guidelines = guidelines_path.read_text() if guidelines_path.exists() else ""

    user_payload = {
        "prompt_path": prompt_path,
        "current_prompt": prompt_text,
        "failures": failure_summary,
        "guardrails": policy.get("prompt_tuning", {}),
        "constraints": {
            "allowed_patch_globs": policy.get("allowed_patch_globs", []),
            "max_prompt_delta_lines": policy.get("prompt_tuning", {}).get("max_prompt_delta_lines", 120),
        }
    }

    msgs = [
        {"role": "system", "content": system},
        {"role": "system", "content": guidelines},
        {"role": "user", "content": json.dumps(user_payload)}
    ]

    out = call_llm(msgs, temperature=0.2, max_tokens=2200)
    
    if isinstance(out, dict) and "updated_prompt" in out:
        return out["updated_prompt"]
    if isinstance(out, str):
        return out
    raise RuntimeError("Prompt tuner returned unexpected format.")
