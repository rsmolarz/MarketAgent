import json
import yaml
import subprocess
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.llm_client import call_llm
from meta.safe_patch_apply import apply_patch, PatchError
from eval.harness import run_suite

PROTECTED_PREFIXES = (
    ".github/",
    "infra/",
    "secrets/",
    "trading/",
    "allocation/",
    "tools/",
)

def git(cmd):
    try:
        return subprocess.check_output(["bash", "-lc", cmd], text=True, stderr=subprocess.DEVNULL).strip()
    except subprocess.CalledProcessError:
        return ""

def is_clean_git():
    return git("git status --porcelain") == ""

def reset_hard():
    git("git reset --hard HEAD")

def collect_editable_agents(manifest):
    return [
        a for a in manifest["agents"]
        if a.get("sandbox_editable") and not a.get("execution_sensitive")
    ]

def run_all_evals(manifest):
    failures = []
    for a in manifest["agents"]:
        out = f"eval/results/{a['name']}.json"
        try:
            results = run_suite(
                module=a["module"],
                callable_name=a["callable"],
                suite_path=a["eval_suite"],
                out_path=out,
                eval_adapter=a.get("eval_adapter")
            )
            if any(not r["ok"] for r in results):
                failures.append(a["name"])
        except Exception as e:
            print(f"Warning: Could not run eval for {a['name']}: {e}")
            failures.append(a["name"])
    return failures

def main():
    if not is_clean_git():
        print("Warning: Git working tree is not clean. Proceeding with caution.")

    manifest_path = Path("agents/manifest.yaml")
    if not manifest_path.exists():
        print("Error: agents/manifest.yaml not found")
        return

    manifest = yaml.safe_load(manifest_path.read_text())
    editable = collect_editable_agents(manifest)

    if not editable:
        print("No sandbox-editable agents found.")
        return

    payload = {
        "editable_agents": [
            {
                "name": a["name"],
                "module": a["module"],
                "callable": a["callable"]
            } for a in editable
        ],
        "constraints": {
            "allowed_root": "agents/",
            "forbidden_prefixes": list(PROTECTED_PREFIXES),
            "max_files_changed": 4,
            "max_lines_changed": 200,
            "no_new_dependencies": True,
            "no_execution_logic_changes": True
        },
        "required_output": {
            "patch": "unified diff only"
        }
    }

    msgs = [
        {
            "role": "system",
            "content": (
                "You are operating in a SANDBOX.\n"
                "You may propose improvements ONLY for analysis-only agents.\n"
                "Output STRICT JSON: {\"patch\":\"<unified diff>\"}\n"
                "Any violation causes rejection."
            )
        },
        {"role": "user", "content": json.dumps(payload)}
    ]

    try:
        response = call_llm(msgs, temperature=0.2, max_tokens=2200)
    except Exception as e:
        print(f"LLM call failed: {e}")
        return

    patch = response.get("patch")
    if not patch:
        print("No patch proposed.")
        return

    print("Applying sandbox patch...")
    try:
        apply_patch(
            patch_text=patch,
            max_files=4,
            max_lines=200,
            allowed_root="agents/"
        )
    except PatchError as e:
        reset_hard()
        print(f"Patch rejected: {e}")
        return
    except Exception as e:
        reset_hard()
        print(f"Patch application failed: {e}")
        return

    print("Running evals after patch...")
    failures = run_all_evals(manifest)
    if failures:
        reset_hard()
        print(f"Sandbox patch failed evals: {failures}")
        print("Changes rolled back.")
        return

    git("git add agents/")
    git('git commit -m "Sandbox: analysis-agent self-improvement (eval-verified)"')

    print("Sandbox patch applied and committed successfully.")

if __name__ == "__main__":
    main()
