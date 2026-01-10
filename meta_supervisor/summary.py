import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

def build_exec_summary():
    report = json.loads(Path("meta_supervisor/reports/meta_report.json").read_text())

    fleet = report.get("fleet", {})
    agents = report.get("agents", {})

    subject = (
        f"[Meta-Agent] Portfolio PnL {fleet.get('portfolio_pnl_bps',0)} bps | "
        f"Hit {fleet.get('portfolio_hit_rate',0)} | "
        f"Severity {report.get('meta',{}).get('severity','low')}"
    )

    lines = []
    lines.append("META-AGENT EXECUTIVE SUMMARY")
    lines.append("")
    lines.append(f"Generated: {report.get('meta',{}).get('generated_at','')}")
    lines.append("")
    lines.append("PORTFOLIO")
    lines.append(f"- PnL (bps): {fleet.get('portfolio_pnl_bps',0)}")
    lines.append(f"- Hit rate: {fleet.get('portfolio_hit_rate',0)}")
    lines.append(f"- Max drawdown (bps): {fleet.get('portfolio_max_drawdown_bps',0)}")
    lines.append("")

    lines.append("AGENTS (top contributors)")
    ranked = sorted(
        agents.items(),
        key=lambda kv: kv[1].get("pnl_sum_bps", 0),
        reverse=True
    )[:6]

    for name, a in ranked:
        lines.append(
            f"- {name}: "
            f"PnL={a.get('pnl_sum_bps','')}bps | "
            f"Hit={a.get('hit_rate','')} | "
            f"Decision={a.get('decision','HOLD')}"
        )

    text_body = "\n".join(lines)

    html_body = (
        "<h2>Meta-Agent Executive Summary</h2>"
        f"<p><b>Generated:</b> {report.get('meta',{}).get('generated_at','')}</p>"
        f"<p><b>Portfolio PnL (bps):</b> {fleet.get('portfolio_pnl_bps',0)}</p>"
        f"<p><b>Hit rate:</b> {fleet.get('portfolio_hit_rate',0)}</p>"
        f"<p><b>Max DD (bps):</b> {fleet.get('portfolio_max_drawdown_bps',0)}</p>"
        "<h3>Top Agents</h3>"
        "<ul>" +
        "".join(
            f"<li><b>{name}</b>: "
            f"PnL {a.get('pnl_sum_bps','')}bps | "
            f"Hit {a.get('hit_rate','')} | "
            f"{a.get('decision','HOLD')}</li>"
            for name,a in ranked
        ) +
        "</ul>"
    )

    return subject, text_body, html_body


if __name__ == "__main__":
    subject, text, html = build_exec_summary()
    print(f"Subject: {subject}")
    print()
    print(text)
