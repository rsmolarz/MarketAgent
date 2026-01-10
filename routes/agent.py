import os
import uuid
import subprocess
import logging
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, abort
from flask_login import current_user

logger = logging.getLogger(__name__)


def _get_agent_store():
    """Lazy import to avoid circular imports."""
    from services.agent_store import (
        list_proposals, get_proposal, get_votes, store_proposal,
        add_vote, reject_proposal, mark_status, previously_rejected_reason
    )
    return {
        'list_proposals': list_proposals,
        'get_proposal': get_proposal,
        'get_votes': get_votes,
        'store_proposal': store_proposal,
        'add_vote': add_vote,
        'reject_proposal': reject_proposal,
        'mark_status': mark_status,
        'previously_rejected_reason': previously_rejected_reason
    }


def _get_services():
    """Lazy import for other services."""
    from services.diff_render import render_side_by_side
    from services.agent_runner import run_validator, run_compliance, run_builder_agent
    from services.pdf_heatmap import annotate_pdf_with_clauses, ClauseHit
    from services.risk_scoring import score_diff
    from services.confidence_decay import decay, is_stale
    from services.approval_report import build_approval_report_pdf
    return {
        'render_side_by_side': render_side_by_side,
        'run_validator': run_validator,
        'run_compliance': run_compliance,
        'run_builder_agent': run_builder_agent,
        'annotate_pdf_with_clauses': annotate_pdf_with_clauses,
        'ClauseHit': ClauseHit,
        'score_diff': score_diff,
        'decay': decay,
        'is_stale': is_stale,
        'build_approval_report_pdf': build_approval_report_pdf
    }

agent_bp = Blueprint("agent", __name__, url_prefix="/admin/agents")


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
            abort(403)
        return f(*args, **kwargs)
    return wrapper


@agent_bp.before_request
def protect_admin_agents():
    if not current_user.is_authenticated:
        return redirect(url_for('replit_auth.login'))
    if not getattr(current_user, 'is_admin', False):
        abort(403)


@agent_bp.get("/")
def agent_dashboard():
    store = _get_agent_store()
    return render_template("agent_dashboard.html", proposals=store['list_proposals'](50))


@agent_bp.get("/proposals/<pid>")
def agent_proposal_detail(pid):
    store = _get_agent_store()
    svc = _get_services()
    p = store['get_proposal'](pid)
    if not p:
        flash("Proposal not found.", "danger")
        return redirect(url_for("agent.agent_dashboard"))

    votes = store['get_votes'](pid)
    
    for v in votes:
        conf = float(v.get("confidence", 0))
        created = v.get("created_at", "")
        v["effective_confidence"] = svc['decay'](conf, created)
        v["is_stale"] = svc['is_stale'](conf, created)
    
    diff_html = svc['render_side_by_side'](p["unified_diff"])
    return render_template(
        "agent_proposal_detail.html",
        proposal=p,
        votes=votes,
        diff_html=diff_html
    )


@agent_bp.post("/proposals/<pid>/run-votes")
def agent_run_votes(pid):
    store = _get_agent_store()
    svc = _get_services()
    p = store['get_proposal'](pid)
    if not p:
        flash("Proposal not found.", "danger")
        return redirect(url_for("agent.agent_dashboard"))

    v = svc['run_validator'](p["unified_diff"])
    c = svc['run_compliance'](p["unified_diff"])

    store['add_vote'](pid, "VALIDATOR", v.get("vote", "REJECT"), float(v.get("confidence", 0.5)), v.get("notes", ""))
    store['add_vote'](pid, "COMPLIANCE", c.get("vote", "REJECT"), float(c.get("confidence", 0.5)), c.get("notes", ""))

    flash("Votes recorded (Validator + Compliance).", "success")
    return redirect(url_for("agent.agent_proposal_detail", pid=pid))


def _run_tests() -> bool:
    try:
        result = subprocess.run(["pytest", "-q"], capture_output=True, timeout=120)
        return result.returncode == 0
    except Exception as e:
        logger.warning(f"Test run failed: {e}")
        return False


def _get_git_diff() -> str:
    try:
        result = subprocess.run(
            ["git", "diff", "--cached"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.stdout.strip():
            return result.stdout
        result = subprocess.run(
            ["git", "diff"],
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.stdout
    except Exception as e:
        logger.error(f"Failed to get git diff: {e}")
        return ""


@agent_bp.post("/proposals/<pid>/approve-merge")
def agent_approve_merge(pid):
    store = _get_agent_store()
    svc = _get_services()
    p = store['get_proposal'](pid)
    if not p:
        flash("Proposal not found.", "danger")
        return redirect(url_for("agent.agent_dashboard"))

    votes = store['get_votes'](pid)
    
    for v in votes:
        conf = float(v.get("confidence", 0))
        created = v.get("created_at", "")
        v["effective_confidence"] = svc['decay'](conf, created)
    
    approvals = [x for x in votes if x["vote"] == "APPROVE" and x["agent_name"] in ("VALIDATOR", "COMPLIANCE")]
    if len(approvals) < 2:
        flash("Cannot merge: missing approvals from Validator and Compliance.", "danger")
        return redirect(url_for("agent.agent_proposal_detail", pid=pid))
    
    stale_approvals = [x for x in approvals if x["effective_confidence"] < 0.55]
    if stale_approvals:
        stale_names = [x["agent_name"] for x in stale_approvals]
        flash(f"Cannot merge: approvals from {', '.join(stale_names)} are stale; re-run votes.", "danger")
        return redirect(url_for("agent.agent_proposal_detail", pid=pid))

    if float(p["overall_risk"]) >= 0.75:
        flash("Blocked: risk score too high for auto-merge. Review manually.", "danger")
        store['mark_status'](pid, "BLOCKED")
        return redirect(url_for("agent.agent_proposal_detail", pid=pid))

    try:
        subprocess.run(["git", "checkout", "main"], check=True, capture_output=True)
        subprocess.run(["git", "pull"], capture_output=True)

        subprocess.run(
            ["git", "merge", "--no-ff", p["branch"], "-m", f"Merge agent proposal {pid}: {p['title']}"],
            check=True,
            capture_output=True
        )

        if not _run_tests():
            subprocess.run(["git", "reset", "--hard", "HEAD~1"], check=True, capture_output=True)
            flash("Tests failed after merge; merge reverted.", "danger")
            store['mark_status'](pid, "BLOCKED")
            return redirect(url_for("agent.agent_proposal_detail", pid=pid))

        store['mark_status'](pid, "MERGED")
        flash("Merged to main successfully.", "success")
        return redirect(url_for("agent.agent_proposal_detail", pid=pid))

    except Exception as e:
        flash(f"Merge failed: {e}", "danger")
        store['mark_status'](pid, "BLOCKED")
        return redirect(url_for("agent.agent_proposal_detail", pid=pid))


@agent_bp.post("/proposals/<pid>/reject")
def agent_reject(pid):
    store = _get_agent_store()
    reason = request.form.get("reason", "").strip() or "Rejected without reason."
    store['reject_proposal'](pid, reason)
    flash("Proposal rejected and stored in agent memory.", "success")
    return redirect(url_for("agent.agent_proposal_detail", pid=pid))


@agent_bp.post("/proposals/<pid>/heatmap")
def agent_heatmap(pid):
    svc = _get_services()
    pdf_path = request.form.get("pdf_path", "").strip()
    if not pdf_path or not os.path.exists(pdf_path):
        flash("PDF not found on server.", "danger")
        return redirect(url_for("agent.agent_proposal_detail", pid=pid))

    ClauseHit = svc['ClauseHit']
    hits = [
        ClauseHit("Governing Law", request.form.get("governing_law_text", "")),
        ClauseHit("Venue / Forum", request.form.get("venue_text", "")),
        ClauseHit("Personal Guarantee", request.form.get("guarantee_text", "")),
    ]

    out_path = svc['annotate_pdf_with_clauses'](pdf_path, hits, out_dir="uploads")
    return send_file(out_path, as_attachment=True)


@agent_bp.post("/autobuild")
def autobuild():
    """
    Builder Agent proposes a change.
    NEVER touches main.
    """
    store = _get_agent_store()
    svc = _get_services()
    goal = request.form.get("goal", "").strip()
    if not goal:
        flash("Please provide a goal for the agent.", "danger")
        return redirect(url_for("agent.agent_dashboard"))

    branch = f"agent/{uuid.uuid4().hex[:8]}"
    
    try:
        subprocess.run(["git", "stash"], capture_output=True)
        subprocess.run(["git", "checkout", "-b", branch], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        flash(f"Failed to create branch: {e}", "danger")
        return redirect(url_for("agent.agent_dashboard"))

    try:
        repo_context = _get_repo_context()
        rejected_hint = store['previously_rejected_reason'](goal)
        
        proposal = svc['run_builder_agent'](goal, repo_context, rejected_hint)
        
        if proposal.get("files_to_change"):
            _apply_proposal_changes(proposal)
        
        diff = _get_git_diff()
        
        if not diff.strip():
            subprocess.run(["git", "checkout", "main"], capture_output=True)
            subprocess.run(["git", "branch", "-D", branch], capture_output=True)
            flash("Agent produced no changes. Try a different goal.", "warning")
            return redirect(url_for("agent.agent_dashboard"))
        
        file_risk, overall_risk = svc['score_diff'](diff)
        
        pid = uuid.uuid4().hex
        store['store_proposal'](
            pid=pid,
            branch=branch,
            title=proposal.get("title", goal[:50]),
            summary=proposal.get("summary", "Agent-generated proposal"),
            rationale=proposal.get("rationale", "Automated improvement"),
            unified_diff=diff,
            overall_risk=overall_risk,
            file_risk=file_risk
        )

        subprocess.run(["git", "add", "-A"], capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", f"Agent proposal: {proposal.get('title', goal[:50])}"],
            capture_output=True
        )
        subprocess.run(["git", "checkout", "main"], capture_output=True)

        flash("Agent proposal created successfully.", "success")
        return redirect(url_for("agent.agent_proposal_detail", pid=pid))

    except Exception as e:
        logger.error(f"Autobuild failed: {e}")
        subprocess.run(["git", "checkout", "main"], capture_output=True)
        subprocess.run(["git", "branch", "-D", branch], capture_output=True)
        flash(f"Agent build failed: {e}", "danger")
        return redirect(url_for("agent.agent_dashboard"))


def _get_repo_context() -> str:
    try:
        result = subprocess.run(
            ["find", ".", "-name", "*.py", "-type", "f", "-not", "-path", "./.git/*"],
            capture_output=True,
            text=True,
            timeout=10
        )
        files = result.stdout.strip().split("\n")[:20]
        
        context_parts = []
        for f in files:
            if f:
                context_parts.append(f"- {f}")
        
        return "Python files in repo:\n" + "\n".join(context_parts)
    except Exception:
        return "Unable to read repo context"


def _apply_proposal_changes(proposal: dict):
    """
    Apply file changes from Builder Agent proposal.
    
    The proposal contains files_to_change with full file contents.
    
    SECURITY: All paths are validated to prevent traversal attacks.
    """
    from pathlib import Path
    
    repo_root = Path.cwd().resolve()
    
    BLOCKED_PATHS = {
        '.git', '.env', '.bashrc', '.profile', '.ssh',
        'etc', 'proc', 'sys', 'dev', 'tmp', 'var', 'root'
    }
    BLOCKED_EXTENSIONS = {'.sh', '.bash', '.zsh', '.env', '.pem', '.key'}
    
    files_to_change = proposal.get("files_to_change", [])
    
    for file_info in files_to_change:
        path = file_info.get("path", "")
        content = file_info.get("content", "")
        
        if not path or not content:
            continue
        
        try:
            target = (repo_root / path).resolve()
            
            try:
                target.relative_to(repo_root)
            except ValueError:
                logger.error(f"SECURITY: Path traversal blocked for: {path}")
                continue
            
            path_parts = set(target.parts)
            if path_parts & BLOCKED_PATHS:
                logger.error(f"SECURITY: Blocked path segment in: {path}")
                continue
            
            if target.suffix.lower() in BLOCKED_EXTENSIONS:
                logger.error(f"SECURITY: Blocked file extension: {path}")
                continue
            
            if '..' in path:
                logger.error(f"SECURITY: Relative path component blocked: {path}")
                continue
            
            dir_path = target.parent
            if dir_path != repo_root:
                dir_path.mkdir(parents=True, exist_ok=True)
            
            with open(target, 'w') as f:
                f.write(content)
            
            logger.info(f"Applied change to: {path}")
        except Exception as e:
            logger.error(f"Failed to apply change to {path}: {e}")


@agent_bp.get("/proposals/<pid>/report.pdf")
def approval_report_pdf(pid):
    """Generate and download PDF approval report with voting details."""
    store = _get_agent_store()
    svc = _get_services()
    p = store['get_proposal'](pid)
    if not p:
        flash("Proposal not found.", "danger")
        return redirect(url_for("agent.agent_dashboard"))
    
    votes = store['get_votes'](pid)
    
    for v in votes:
        conf = float(v.get("confidence", 0))
        created = v.get("created_at", "")
        v["effective_confidence"] = svc['decay'](conf, created)
    
    os.makedirs("uploads", exist_ok=True)
    out_path = os.path.join("uploads", f"approval_report_{pid}.pdf")
    
    svc['build_approval_report_pdf'](out_path, p, votes)
    
    return send_file(
        out_path, 
        as_attachment=True, 
        download_name=f"approval_report_{pid}.pdf",
        mimetype="application/pdf"
    )
