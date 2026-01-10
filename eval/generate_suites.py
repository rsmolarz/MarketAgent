import json
import yaml
from pathlib import Path

DEFAULT_CASES = [
    {
        "id": "smoke_1",
        "input": {"text": "Return a one-sentence summary."}
    },
    {
        "id": "smoke_2",
        "input": {"text": "List 3 risks and 3 mitigations."}
    },
]

def infer_suite_name(agent_name: str) -> str:
    return f"eval/suites/{agent_name}.jsonl"

def main():
    manifest = yaml.safe_load(Path("agents/manifest.yaml").read_text())
    Path("eval/suites").mkdir(parents=True, exist_ok=True)

    for a in manifest["agents"]:
        suite_path = Path(a.get("eval_suite") or infer_suite_name(a["name"]))
        if suite_path.exists():
            print(f"Suite exists: {suite_path}")
            continue

        lines = []
        for c in DEFAULT_CASES:
            lines.append(json.dumps(c))

        suite_path.write_text("\n".join(lines) + "\n")
        print(f"Created {suite_path}")

if __name__ == "__main__":
    main()
