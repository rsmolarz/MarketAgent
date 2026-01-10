import json
import yaml
from pathlib import Path

from eval.harness import run_suite
from meta.prompt_variant_manager import ensure_variants, load_variant, save_champion

def _set_prompt_text(prompt_path: str, text: str):
    Path(prompt_path).write_text(text)

def run_all_evals(manifest):
    summaries = {}
    for a in manifest["agents"]:
        out = f"eval/results/{a['name']}.json"
        results = run_suite(
            module=a["module"],
            callable_name=a["callable"],
            suite_path=a["eval_suite"],
            out_path=out,
            eval_adapter=a.get("eval_adapter")
        )
        total = len(results)
        passed = sum(1 for r in results if r["ok"])
        summaries[a["name"]] = {"total": total, "passed": passed, "success_rate": passed / max(total, 1)}
    global_score = sum(v["success_rate"] for v in summaries.values()) / max(len(summaries), 1)
    return global_score, summaries

def ab_test_prompts(prompt_paths, min_trials=1, promote_if_delta=0.01):
    manifest = yaml.safe_load(Path("agents/manifest.yaml").read_text())

    report = {"tests": []}

    for prompt_path in prompt_paths:
        if not Path(prompt_path).exists():
            continue
            
        ensure_variants(prompt_path)

        A = load_variant(prompt_path, "A")
        B = load_variant(prompt_path, "B")

        _set_prompt_text(prompt_path, A)
        score_A, detail_A = run_all_evals(manifest)

        _set_prompt_text(prompt_path, B)
        score_B, detail_B = run_all_evals(manifest)

        delta = score_B - score_A
        winner = "B" if delta > 0 else "A"

        report["tests"].append({
            "prompt": prompt_path,
            "score_A": score_A,
            "score_B": score_B,
            "delta_B_minus_A": delta,
            "winner": winner,
            "detail_A": detail_A,
            "detail_B": detail_B
        })

        if abs(delta) >= promote_if_delta:
            champion_text = B if winner == "B" else A
            save_champion(prompt_path, champion_text)
        else:
            champ = load_variant(prompt_path, "champion")
            _set_prompt_text(prompt_path, champ)

    Path("meta/reports").mkdir(parents=True, exist_ok=True)
    Path("meta/reports/ab_test_report.json").write_text(json.dumps(report, indent=2))
    return report

if __name__ == "__main__":
    prompts = [
        "agents/prompts/meta_system.md",
        "agents/prompts/reviewer.md",
        "agents/prompts/agent_guidelines.md"
    ]
    ab_test_prompts(prompts)
