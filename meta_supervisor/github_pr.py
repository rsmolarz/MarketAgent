import os
import json
import logging
import base64
import requests
import yaml
from pathlib import Path
from datetime import datetime, timezone

from meta_supervisor.auto_revert import find_reverts, apply_reverts_to_yaml
from meta_supervisor.capital_at_risk import capital_deltas, snapshot_prev

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
REPO = os.environ.get("GITHUB_REPO")
TOKEN = os.environ.get("GITHUB_TOKEN")
BASE = "main"
HEAD = "meta/promotions"


def _headers():
    return {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json"
    }


def _get_file_sha(path: str) -> str | None:
    """Get SHA of existing file on HEAD branch"""
    if not REPO or not TOKEN:
        return None
    url = f"{GITHUB_API}/repos/{REPO}/contents/{path}?ref={HEAD}"
    r = requests.get(url, headers=_headers())
    if r.status_code == 200:
        return r.json().get("sha")
    return None


def commit_file(path: str, content: str, message: str) -> dict | None:
    """Create or update a file on HEAD branch"""
    if not REPO or not TOKEN:
        logger.warning("GITHUB_REPO or GITHUB_TOKEN not set, cannot commit file")
        return None

    url = f"{GITHUB_API}/repos/{REPO}/contents/{path}"
    encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    
    payload = {
        "message": message,
        "content": encoded_content,
        "branch": HEAD,
    }

    sha = _get_file_sha(path)
    if sha:
        payload["sha"] = sha

    try:
        r = requests.put(url, headers=_headers(), json=payload)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error(f"Failed to commit file {path}: {e}")
        return None


def create_branch_if_not_exists():
    """Create the meta/promotions branch if it doesn't exist"""
    if not REPO or not TOKEN:
        return False
    
    try:
        ref_url = f"{GITHUB_API}/repos/{REPO}/git/ref/heads/{BASE}"
        r = requests.get(ref_url, headers=_headers())
        if r.status_code != 200:
            logger.error(f"Failed to get base branch: {r.status_code}")
            return False
        
        sha = r.json()["object"]["sha"]
        
        check_url = f"{GITHUB_API}/repos/{REPO}/git/ref/heads/{HEAD.replace('/', '%2F')}"
        r = requests.get(check_url, headers=_headers())
        if r.status_code == 200:
            return True
        
        create_url = f"{GITHUB_API}/repos/{REPO}/git/refs"
        payload = {
            "ref": f"refs/heads/{HEAD}",
            "sha": sha
        }
        r = requests.post(create_url, headers=_headers(), json=payload)
        return r.status_code in (200, 201)
    except Exception as e:
        logger.error(f"Failed to create branch: {e}")
        return False


def create_pr(title: str, body: str):
    """Create a GitHub PR"""
    if not REPO or not TOKEN:
        logger.warning("GITHUB_REPO or GITHUB_TOKEN not set, cannot create PR")
        return None
    
    url = f"{GITHUB_API}/repos/{REPO}/pulls"
    payload = {
        "title": title,
        "head": HEAD,
        "base": BASE,
        "body": body
    }
    
    try:
        r = requests.post(url, headers=_headers(), json=payload)
        if r.status_code == 422:
            logger.info("PR already exists or no changes")
            return {"status": "exists", "message": r.json().get("message", "")}
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error(f"Failed to create PR: {e}")
        return None


def md_table(headers, rows):
    """Generate IC-style markdown table"""
    def esc(x):
        s = "" if x is None else str(x)
        return s.replace("\n", " ").replace("|", "\\|")
    out = []
    out.append("| " + " | ".join(map(esc, headers)) + " |")
    out.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for r in rows:
        out.append("| " + " | ".join(esc(c) for c in r) + " |")
    return "\n".join(out)


def update_strategy_kill_list(breaches: list) -> str:
    """Update strategy_kill_list.yaml with breached strategies"""
    path = Path("meta_supervisor/strategy_kill_list.yaml")
    current = {}
    if path.exists():
        try:
            current = yaml.safe_load(path.read_text()) or {}
        except Exception:
            current = {}

    for b in breaches:
        s = b["strategy"]
        current[s] = {
            "status": "DISABLED",
            "reason": "; ".join(b["reasons"]),
            "disabled_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }

    return yaml.dump(current, default_flow_style=False)


def maybe_create_pr(report: dict) -> dict | None:
    """Create PR if there are promotion, retirement, strategy breach, or revert decisions"""
    if not create_branch_if_not_exists():
        logger.error("Failed to ensure promotion branch")
        return None

    agents = report.get("agents", {})
    meta = report.get("meta", {})
    
    promote = [a for a, v in agents.items() if v.get("decision") == "PROMOTE"]
    retire = [a for a, v in agents.items() if v.get("decision") in ("RETIRE", "KILL")]
    
    strategy_report = {}
    try:
        p = Path("meta_supervisor/state/strategy_attribution.json")
        if p.exists():
            strategy_report = json.loads(p.read_text())
    except Exception:
        pass

    breaches = strategy_report.get("breaches", [])
    
    reverts = find_reverts()
    
    if not promote and not retire and not breaches and not reverts:
        logger.info("No promotions, retirements, breaches, or reverts, skipping PR creation")
        return None
    
    body_parts = [
        "## Meta-Supervisor Review",
        f"**Generated:** {meta.get('generated_at', '')}",
        f"**Severity:** {meta.get('severity', 'unknown')}",
        "",
    ]
    
    if breaches:
        body_parts.append("### 🚨 STRATEGY DISABLES (CVaR BREACH)")
        rows = [[b["strategy"], b.get("pnl_sum_bps", 0), b.get("hit_rate", 0), ", ".join(b.get("reasons", []))] for b in breaches]
        body_parts.append(md_table(["Strategy", "PnL (bps)", "Hit Rate", "Reason"], rows))
        body_parts.append("")

        yaml_body = update_strategy_kill_list(breaches)
        commit_file(
            path="meta_supervisor/strategy_kill_list.yaml",
            content=yaml_body,
            message="[AUTO] Disable breached strategy classes"
        )
    
    if reverts:
        body_parts.append("### ✅ STRATEGY RE-ENABLES (RECOVERED)")
        rows = [[r["strategy"], r["metrics"].get("mean_abs_error_bps"), r["metrics"].get("cvar95_error_bps"), r["metrics"].get("n")] for r in reverts]
        body_parts.append(md_table(["Strategy", "Mean Abs Error (bps)", "CVaR95 Error (bps)", "Trade Count"], rows))
        body_parts.append("")

        yaml_body = apply_reverts_to_yaml(reverts)
        commit_file(
            path="meta_supervisor/strategy_kill_list.yaml",
            content=yaml_body,
            message="[AUTO-REVERT] Re-enable recovered strategy classes"
        )
    
    if promote:
        body_parts.append("### ✅ PROMOTIONS (IC View)")
        rows = []
        for a in promote:
            s = agents.get(a, {})
            rows.append([a, s.get("pnl_sum_bps"), s.get("hit_rate"), s.get("avg_latency_ms"), s.get("cost_usd")])
        body_parts.append(md_table(["Agent", "PnL (bps)", "Hit", "Latency (ms)", "Cost ($)"], rows))
        body_parts.append("")

        commit_file(
            path="meta_supervisor/state/promoted_agents.json",
            content=json.dumps({
                "generated_at": meta.get("generated_at"),
                "agents": promote
            }, indent=2),
            message="[AUTO] Mark agents as promotable"
        )
    
    if retire:
        body_parts.append("### ❌ RETIREMENTS (IC View)")
        rows = []
        for a in retire:
            s = agents.get(a, {})
            rows.append([a, s.get("decision", "RETIRE"), s.get("retirement_score", 0), s.get("pnl_sum_bps"), s.get("hit_rate")])
        body_parts.append(md_table(["Agent", "Decision", "Retire Score", "PnL (bps)", "Hit"], rows))
        body_parts.append("")
    
    total_cap = float(os.environ.get("TOTAL_CAPITAL_USD", "100000"))
    deltas = capital_deltas(total_cap)
    if deltas:
        body_parts.append("### 💰 CAPITAL-AT-RISK DELTAS")
        rows = [[r["agent"], r["prev_w"], r["cur_w"], r["delta_w"], r["delta_capital_usd"], r["capital_usd"]] for r in deltas[:10]]
        body_parts.append(md_table(["Agent", "Prev W", "Cur W", "ΔW", "ΔCapital ($)", "Capital ($)"], rows))
        body_parts.append("")
    
    body_parts.extend([
        "---",
        "*This PR was auto-generated by the Meta-Supervisor.*",
        "*Human review required before merge.*"
    ])
    
    title_parts = []
    if len(reverts) > 0:
        title_parts.append(f"{len(reverts)} Reverts")
    if len(breaches) > 0:
        title_parts.append(f"{len(breaches)} Strategy Disables")
    if len(promote) > 0:
        title_parts.append(f"{len(promote)} Promotions")
    if len(retire) > 0:
        title_parts.append(f"{len(retire)} Retirements")
    
    title = f"[AUTO] Meta-Supervisor: {' / '.join(title_parts)}"
    body = "\n".join(body_parts)
    
    result = create_pr(title, body)
    
    snapshot_prev()
    
    log_path = Path("meta_supervisor/state/pr_log.json")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    log_entry = {
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "promotions": promote,
        "retirements": retire,
        "strategy_breaches": [b["strategy"] for b in breaches],
        "strategy_reverts": [r["strategy"] for r in reverts],
        "pr_result": result,
    }
    
    existing_log = []
    if log_path.exists():
        try:
            existing_log = json.loads(log_path.read_text())
        except Exception:
            existing_log = []
    
    existing_log.append(log_entry)
    log_path.write_text(json.dumps(existing_log[-50:], indent=2))
    
    return result


if __name__ == "__main__":
    report_path = Path("meta_supervisor/reports/meta_report.json")
    if report_path.exists():
        report = json.loads(report_path.read_text())
        result = maybe_create_pr(report)
        print(json.dumps(result, indent=2) if result else "No PR created")
