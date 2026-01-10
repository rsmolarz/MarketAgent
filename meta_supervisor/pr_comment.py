import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

def render_pr_comment(report: dict) -> str:
    meta = report.get("meta", {})
    agents = report.get("agents", {})
    fleet = report.get("fleet", {})

    lines = []
    lines.append("## 🤖 Meta-Agent Review")
    lines.append(f"_Generated: {meta.get('generated_at','')} | Severity: **{meta.get('severity','low')}**_")
    lines.append("")

    if fleet:
        lines.append("### Portfolio")
        lines.append(
            f"- PnL (bps): **{fleet.get('portfolio_pnl_bps')}** | "
            f"Hit rate: **{fleet.get('portfolio_hit_rate')}** | "
            f"Max DD (bps): **{fleet.get('portfolio_max_drawdown_bps')}**"
        )
        lines.append("")

    lines.append("### Agents")
    lines.append("| Agent | Runs | Avg Latency (ms) | Alpha Signals | Decision |")
    lines.append("|------|------|------------------|---------------|----------|")

    for name, a in agents.items():
        lines.append(
            f"| `{name}` | {a.get('runs',0)} | {a.get('avg_latency_ms','')} | "
            f"{a.get('alpha_signals',0)} | {a.get('decision','HOLD')} |"
        )

    lines.append("")
    lines.append("<details><summary>Raw Meta Report</summary>\n```json")
    lines.append(json.dumps(report, indent=2))
    lines.append("```\n</details>")

    return "\n".join(lines)


if __name__ == "__main__":
    report = json.loads(Path("meta_supervisor/reports/meta_report.json").read_text())
    print(render_pr_comment(report))
