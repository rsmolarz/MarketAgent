import json
import logging
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.llm_client import call_llm

CRITIQUE_PAIRS = [
    ("macro_watcher", "geopolitical_risk"),
    ("geopolitical_risk", "macro_watcher"),
    ("arbitrage_finder", "macro_watcher"),
]

CRITIQUE_SCHEMA = {
    "type": "object",
    "properties": {
        "strengths": {"type": "array", "items": {"type": "string"}},
        "weaknesses": {"type": "array", "items": {"type": "string"}},
        "suggestions": {"type": "array", "items": {"type": "string"}},
        "prompt_improvements": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number"}
    }
}

def load_latest_output(agent_name: str) -> dict:
    path = Path(f"eval/results/{agent_name}.json")
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        return data
    except (json.JSONDecodeError, IOError) as e:
        logging.debug(f"Failed to load output for {agent_name}: {e}")
        return {}

def run_critique(critic_agent: str, target_agent: str) -> dict:
    target_output = load_latest_output(target_agent)
    
    if not target_output:
        return {"error": f"No output found for {target_agent}"}
    
    msgs = [
        {
            "role": "system",
            "content": (
                f"You are the {critic_agent} agent reviewing the output of {target_agent}.\n"
                "Analyze the output for:\n"
                "1. Quality and accuracy of signals\n"
                "2. Potential blind spots or missed opportunities\n"
                "3. Correlation with your domain expertise\n"
                "4. Suggestions for improvement\n\n"
                "Output JSON with: strengths, weaknesses, suggestions, prompt_improvements, confidence (0-1)"
            )
        },
        {
            "role": "user",
            "content": json.dumps({
                "target_agent": target_agent,
                "output": target_output
            })
        }
    ]
    
    try:
        response = call_llm(msgs, temperature=0.3, max_tokens=1500)
        return response
    except Exception as e:
        return {"error": str(e)}

def run_all_critiques() -> dict:
    results = []
    
    for critic, target in CRITIQUE_PAIRS:
        critique = run_critique(critic, target)
        results.append({
            "critic": critic,
            "target": target,
            "critique": critique
        })
    
    report = {"critiques": results}
    
    Path("meta/reports").mkdir(parents=True, exist_ok=True)
    Path("meta/reports/critique_report.json").write_text(json.dumps(report, indent=2))
    
    return report

def extract_prompt_improvements(report: dict) -> list:
    improvements = []
    for c in report.get("critiques", []):
        critique = c.get("critique", {})
        if isinstance(critique, dict):
            pi = critique.get("prompt_improvements", [])
            if pi:
                improvements.append({
                    "target": c["target"],
                    "critic": c["critic"],
                    "improvements": pi
                })
    return improvements

if __name__ == "__main__":
    report = run_all_critiques()
    print(json.dumps(report, indent=2))
