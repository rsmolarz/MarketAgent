import json
import yaml
import subprocess
import fnmatch
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.llm_client import call_llm
from telemetry.summarize import summarize as summarize_telemetry

def sh(cmd):
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
    except subprocess.CalledProcessError:
        return ""

def git(cmd):
    try:
        return subprocess.check_output(["bash", "-lc", cmd], text=True, stderr=subprocess.DEVNULL).strip()
    except subprocess.CalledProcessError:
        return ""

def git_diff_summary():
    shortstat = sh(["bash", "-lc", "git diff --shortstat origin/main...HEAD 2>/dev/null || true"])
    names = sh(["bash", "-lc", "git diff --name-only origin/main...HEAD 2>/dev/null || true"])
    return {"shortstat": shortstat, "files": [f for f in names.splitlines() if f]}

def summarize_eval(eval_json_path: Path):
    data = json.loads(eval_json_path.read_text())
    results = data.get("results", [])
    total = len(results)
    passed = sum(1 for r in results if r.get("ok"))
    avg_latency = sum(r.get("latency_s", 0) for r in results) / max(total, 1)
    return {
        "suite": data.get("suite"),
        "module": data.get("module"),
        "total": total,
        "passed": passed,
        "success_rate": passed / max(total, 1),
        "avg_latency_s": avg_latency,
        "failures": [r for r in results if not r.get("ok")][:5],
    }

def build_prompt(policy, diffs, evals, telemetry_summary):
    system_path = Path("agents/prompts/meta_system.md")
    reviewer_path = Path("agents/prompts/reviewer.md")
    
    system = system_path.read_text() if system_path.exists() else \
        "You are the Meta-Agent supervising a multi-agent market intelligence system."
    reviewer = reviewer_path.read_text() if reviewer_path.exists() else \
        "You are a senior AI systems reviewer. Output STRICT JSON only."

    user_payload = {
        "policy": policy,
        "git_diff": diffs,
        "evaluation_results": evals,
        "telemetry": telemetry_summary,
        "rubric": {
            "behavior": 50,
            "reliability": 20,
            "efficiency": 15,
            "code_health": 15
        },
        "instructions": [
            "Flag regressions vs baseline",
            "Prioritize agent correctness and reliability",
            "Recommend fixes with file-level specificity",
            "Return valid JSON only"
        ],
        "output_schema": {
            "severity": "low|medium|high|critical",
            "top_findings": [{"title": "", "evidence": "", "impact": "", "confidence": 0.0}],
            "recommended_changes": [{"change": "", "why": "", "files": [""], "priority": "P0|P1|P2"}],
            "patch_suggestions": [{"diff_hunk": "", "notes": "", "risk": "low|medium|high"}],
            "risk_notes": [""]
        }
    }

    return [
        {"role": "system", "content": system},
        {"role": "system", "content": reviewer},
        {"role": "user", "content": json.dumps(user_payload)}
    ]

def run_reviewer(policy, diffs, evals, telemetry_summary):
    messages = build_prompt(policy, diffs, evals, telemetry_summary)
    return call_llm(messages)

def allowed_prompt_file(path: str, policy: dict) -> bool:
    allowed = policy.get("allowed_patch_globs", [])
    return any(fnmatch.fnmatch(path, g) for g in allowed)

def write_prompt_patch(prompt_path: str, new_text: str):
    Path(prompt_path).write_text(new_text)

def diff_line_count():
    result = git("git diff --numstat | awk '{add+=$1; del+=$2} END {print add+del+0}'")
    try:
        return int(result) if result else 0
    except ValueError:
        return 0

def files_changed_count():
    result = git("git diff --name-only | wc -l")
    try:
        return int(result) if result else 0
    except ValueError:
        return 0

def stage_and_commit(title: str):
    git("git add agents/prompts/*.md || true")
    git(f"git commit -m {json.dumps(title)} || true")

def main():
    policy_path = Path("meta/policy.yaml")
    if not policy_path.exists():
        print("Error: meta/policy.yaml not found")
        return

    policy = yaml.safe_load(policy_path.read_text())
    diff = git_diff_summary()
    telemetry_summary = summarize_telemetry()

    eval_results_dir = Path("eval/results")
    eval_summaries = []
    if eval_results_dir.exists():
        for p in sorted(eval_results_dir.glob("*.json")):
            try:
                eval_summaries.append(summarize_eval(p))
            except Exception as e:
                print(f"Warning: Could not summarize {p}: {e}")

    try:
        review = run_reviewer(policy, diff, eval_summaries, telemetry_summary)
    except Exception as e:
        review = {
            "severity": "unknown",
            "error": str(e),
            "top_findings": [],
            "recommended_changes": [],
            "patch_suggestions": [],
            "risk_notes": [f"LLM call failed: {e}"]
        }

    Path("meta/reports").mkdir(parents=True, exist_ok=True)
    Path("meta/reports/meta_report.json").write_text(json.dumps(review, indent=2))
    Path("meta/reports/meta_report.md").write_text(
        "# Meta-Agent Report\n\n" +
        "```json\n" + json.dumps(review, indent=2) + "\n```\n"
    )

    print("Meta-Agent report generated successfully.")
    print(f"Severity: {review.get('severity', 'unknown')}")
    print(f"Top findings: {len(review.get('top_findings', []))}")
    print(f"Recommended changes: {len(review.get('recommended_changes', []))}")

    thresholds = policy.get("thresholds", {})
    min_success_rate = thresholds.get("min_success_rate", 0.80)
    failures = [e for e in eval_summaries if e["success_rate"] < min_success_rate]

    if policy.get("auto_patch") and policy.get("patch_mode") == "prompts_only":
        from meta.prompt_tuner import tune_prompt
        
        prompt_targets = [
            "agents/prompts/meta_system.md",
            "agents/prompts/reviewer.md",
            "agents/prompts/agent_guidelines.md",
        ]

        patch_budget = policy.get("max_patch", {})
        tuned_any = False

        failure_summary = {
            "eval_summaries": eval_summaries,
            "top_failures": [f.get("failures", []) for f in failures][:3],
            "meta_review": review
        }

        for p in prompt_targets:
            if not Path(p).exists():
                continue
            if not allowed_prompt_file(p, policy):
                continue
            try:
                updated = tune_prompt(p, failure_summary, policy)
                if updated and updated.strip() != Path(p).read_text().strip():
                    write_prompt_patch(p, updated)
                    tuned_any = True
                    print(f"Tuned prompt: {p}")
            except Exception as e:
                print(f"Warning: Could not tune {p}: {e}")

            if files_changed_count() > patch_budget.get("max_files_changed", 6):
                break
            if diff_line_count() > patch_budget.get("max_lines_changed", 250):
                break

        if tuned_any:
            stage_and_commit("Meta-Agent: prompt improvements (prompts-only)")
            print("Committed prompt improvements.")

if __name__ == "__main__":
    main()
