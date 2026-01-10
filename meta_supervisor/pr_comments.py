import json
import os
import logging
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

def generate_pr_comment(run_id: str, report: dict, retirements: dict, promotions: list) -> str:
    """
    Generate a GitHub PR comment from Meta-Agent evaluation results.
    """
    fleet = report.get("fleet", {})
    agents = report.get("agents", {})
    meta = report.get("meta", {})
    
    severity = meta.get("severity", "unknown").upper()
    severity_emoji = "🔴" if severity == "HIGH" else "🟢"
    
    agent_rows = []
    for name, a in sorted(agents.items(), key=lambda x: x[1].get("pnl_sum_bps", 0), reverse=True)[:10]:
        status = a.get("decision", "HOLD")
        status_icon = "✅" if status == "PROMOTE" else ("❌" if status == "KILL" else "⏸️")
        agent_rows.append(
            f"| {name} | {a.get('retirement_score', 0)} | {a.get('pnl_sum_bps', 0)} bps | ${a.get('cost_usd', 0):.4f} | {status_icon} {status} |"
        )
    
    findings = []
    to_kill = retirements.get("to_kill", [])
    for agent in to_kill[:5]:
        findings.append(f"- **{agent['agent']} flagged for retirement**\n  Impact: {agent.get('reason', 'Performance threshold breached')}\n  Evidence: Score {agent.get('score', 0)}")
    
    if not findings:
        findings.append("- No critical findings in this evaluation period")
    
    promo_agents = [p["agent"] for p in promotions]
    kill_agents = [a["agent"] for a in to_kill]
    
    promo_result = "✅ APPROVED" if promotions else "⏸️ NO CANDIDATES"
    if kill_agents:
        promo_result = "❌ BLOCKED (agents flagged for retirement)"
    
    recommendations = []
    for agent in to_kill[:3]:
        recommendations.append(f"- Kill {agent['agent']}: {agent.get('reason', 'threshold breach')} (HIGH)")
    for p in promotions[:3]:
        recommendations.append(f"- Promote {p['agent']}: meets all gates (MEDIUM)")
    if not recommendations:
        recommendations.append("- No immediate actions required (LOW)")
    
    comment = f"""## 🤖 Meta-Agent Review Report

**Overall Severity:** {severity_emoji} {severity}  
**Run ID:** {run_id}  
**Generated:** {meta.get('generated_at', datetime.now(timezone.utc).isoformat())}

---

### 📊 Portfolio Summary
- **PnL (bps):** {fleet.get('portfolio_pnl_bps', 0)}
- **Hit Rate:** {fleet.get('portfolio_hit_rate', 0)}
- **Max Drawdown (bps):** {fleet.get('portfolio_max_drawdown_bps', 0)}

---

### 📈 Agent Health Summary
| Agent | Score | Alpha (realized) | Cost | Status |
|-------|-------|------------------|------|--------|
{chr(10).join(agent_rows)}

---

### ⚠️ Top Findings
{chr(10).join(findings)}

---

### ✅ Promotion Gate
- Behavioral score ≥ 80
- Realized PnL positive
- No safety violations
- Confidence decay stable

**Promotable Agents:** {', '.join(promo_agents) if promo_agents else 'None'}  
**Result:** {promo_result}

---

### 🔧 Recommended Actions
{chr(10).join(recommendations)}

---

*Generated automatically by MarketAgents Meta-Supervisor*
"""
    
    return comment

def post_pr_comment(pr_number: int, comment: str) -> bool:
    """
    Post comment to GitHub PR using GitHub API.
    Requires GITHUB_TOKEN environment variable.
    """
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        logger.warning("GITHUB_TOKEN not set, cannot post PR comment")
        return False
    
    try:
        from github import Github
        
        g = Github(token)
        
        repo_name = os.environ.get("GITHUB_REPO", "")
        if not repo_name:
            logger.warning("GITHUB_REPO not set")
            return False
        
        repo = g.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        pr.create_issue_comment(comment)
        
        logger.info(f"Posted PR comment to PR #{pr_number}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to post PR comment: {e}")
        return False

def save_pr_comment(run_id: str, comment: str):
    """Save PR comment to file for manual review or CI integration."""
    Path("meta_supervisor/pr_comments").mkdir(parents=True, exist_ok=True)
    Path(f"meta_supervisor/pr_comments/{run_id}.md").write_text(comment)
