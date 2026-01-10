import json
import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

logger = logging.getLogger(__name__)

admin_proposals_bp = Blueprint("admin_proposals", __name__, url_prefix="/admin/proposals")


def _get_db():
    """Lazy import to avoid circular imports."""
    from models import db
    return db


def _get_proposal_model():
    """Lazy import to get the Proposal model from agent_store."""
    from services.agent_store import Proposal
    return Proposal


def _get_approval_models():
    """Lazy import for approval-related models."""
    from models import ApprovalEvent, AgentMemory
    return ApprovalEvent, AgentMemory


def _get_agent_store():
    """Lazy import for agent store functions."""
    from services import agent_store
    return agent_store


def _get_git_ops():
    """Lazy import for git operations."""
    from services.git_ops import get_diff_against_main, merge_branch_to_main
    return get_diff_against_main, merge_branch_to_main


def _get_risk_tier(overall_risk: float) -> str:
    """Convert 0-1 risk score to tier."""
    score_100 = int(overall_risk * 100)
    if score_100 <= 24:
        return "LOW"
    elif score_100 <= 59:
        return "MED"
    else:
        return "HIGH"


def require_admin():
    """Check if current user is admin, abort with 403 if not."""
    if not getattr(current_user, "is_admin", False):
        abort(403)


@admin_proposals_bp.before_request
@login_required
def protect_proposals():
    """Ensure all proposal routes require admin access."""
    require_admin()


@admin_proposals_bp.route("/", methods=["GET"])
def list_proposals():
    """List all proposals with filtering."""
    Proposal = _get_proposal_model()
    
    status_filter = request.args.get("status", "")
    
    query = Proposal.query.order_by(Proposal.created_at.desc())
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    proposals = query.limit(100).all()
    
    proposal_list = []
    for p in proposals:
        risk_tier = _get_risk_tier(p.overall_risk)
        proposal_list.append({
            'id': p.id,
            'title': p.title,
            'branch_name': p.branch,
            'status': p.status,
            'risk_score': int(p.overall_risk * 100),
            'risk_tier': risk_tier,
            'created_at': p.created_at,
            'tests_passed': False,
            'diff_text': p.unified_diff
        })
    
    return render_template(
        "admin/proposals_list.html",
        proposals=proposal_list,
        status_filter=status_filter
    )


@admin_proposals_bp.route("/<proposal_id>", methods=["GET"])
def view_proposal(proposal_id: str):
    """View a single proposal with diff and actions."""
    Proposal = _get_proposal_model()
    ApprovalEvent, _ = _get_approval_models()
    
    proposal = Proposal.query.get_or_404(proposal_id)
    
    try:
        events = (ApprovalEvent.query
                  .filter_by(proposal_id=proposal_id)
                  .order_by(ApprovalEvent.created_at.desc())
                  .all())
    except Exception:
        events = []
    
    risk_tier = _get_risk_tier(proposal.overall_risk)
    
    try:
        file_risk = json.loads(proposal.file_risk_json) if proposal.file_risk_json else {}
    except Exception:
        file_risk = {}
    
    proposal_data = {
        'id': proposal.id,
        'title': proposal.title,
        'branch_name': proposal.branch,
        'status': proposal.status,
        'summary': proposal.summary,
        'rationale': proposal.rationale,
        'risk_score': int(proposal.overall_risk * 100),
        'risk_tier': risk_tier,
        'risk_reason': proposal.rationale,
        'file_risk': file_risk,
        'created_at': proposal.created_at,
        'tests_passed': False,
        'test_report': '',
        'diff_text': proposal.unified_diff
    }
    
    return render_template(
        "admin/proposal_detail.html",
        proposal=proposal_data,
        events=events
    )


@admin_proposals_bp.route("/<proposal_id>/refresh-diff", methods=["POST"])
def refresh_diff(proposal_id: str):
    """Refresh the diff from the branch."""
    Proposal = _get_proposal_model()
    db = _get_db()
    get_diff_against_main, _ = _get_git_ops()
    
    proposal = Proposal.query.get_or_404(proposal_id)
    
    try:
        proposal.unified_diff = get_diff_against_main(proposal.branch)
        db.session.commit()
        flash("Diff refreshed successfully.", "success")
    except Exception as e:
        flash(f"Failed to refresh diff: {e}", "danger")
    
    return redirect(url_for("admin_proposals.view_proposal", proposal_id=proposal_id))


@admin_proposals_bp.route("/<proposal_id>/approve", methods=["POST"])
def approve_proposal(proposal_id: str):
    """Approve a proposal."""
    Proposal = _get_proposal_model()
    ApprovalEvent, _ = _get_approval_models()
    db = _get_db()
    
    proposal = Proposal.query.get_or_404(proposal_id)
    rationale = request.form.get("rationale", "").strip()
    
    if proposal.status not in ("PROPOSED", "PENDING", "BLOCKED"):
        flash("Only PROPOSED, PENDING or BLOCKED proposals can be approved.", "warning")
        return redirect(url_for("admin_proposals.view_proposal", proposal_id=proposal_id))
    
    proposal.status = "APPROVED"
    db.session.add(ApprovalEvent(
        proposal_id=str(proposal.id),
        actor_email=current_user.email or "unknown",
        action="APPROVE",
        rationale=rationale
    ))
    db.session.commit()
    
    flash("Proposal approved.", "success")
    return redirect(url_for("admin_proposals.view_proposal", proposal_id=proposal_id))


@admin_proposals_bp.route("/<proposal_id>/reject", methods=["POST"])
def reject_proposal(proposal_id: str):
    """Reject a proposal and store in agent memory."""
    agent_store = _get_agent_store()
    ApprovalEvent, AgentMemory = _get_approval_models()
    db = _get_db()
    
    Proposal = _get_proposal_model()
    proposal = Proposal.query.get_or_404(proposal_id)
    rationale = request.form.get("rationale", "").strip()
    
    if not rationale:
        flash("Please provide a reason for rejection.", "danger")
        return redirect(url_for("admin_proposals.view_proposal", proposal_id=proposal_id))
    
    agent_store.reject_proposal(proposal_id, rationale)
    
    db.session.add(ApprovalEvent(
        proposal_id=str(proposal.id),
        actor_email=current_user.email or "unknown",
        action="REJECT",
        rationale=rationale
    ))
    
    db.session.add(AgentMemory(
        scope="BUILDER",
        key="previous_rejection_reason",
        value=rationale,
        proposal_id=str(proposal.id)
    ))
    
    db.session.commit()
    
    flash("Proposal rejected and stored in agent memory.", "warning")
    return redirect(url_for("admin_proposals.view_proposal", proposal_id=proposal_id))


@admin_proposals_bp.route("/<proposal_id>/block", methods=["POST"])
def block_proposal(proposal_id: str):
    """Block a proposal from being merged."""
    Proposal = _get_proposal_model()
    ApprovalEvent, _ = _get_approval_models()
    db = _get_db()
    
    proposal = Proposal.query.get_or_404(proposal_id)
    rationale = request.form.get("rationale", "").strip()
    
    proposal.status = "BLOCKED"
    db.session.add(ApprovalEvent(
        proposal_id=str(proposal.id),
        actor_email=current_user.email or "unknown",
        action="BLOCK",
        rationale=rationale
    ))
    db.session.commit()
    
    flash("Proposal blocked.", "warning")
    return redirect(url_for("admin_proposals.view_proposal", proposal_id=proposal_id))


@admin_proposals_bp.route("/<proposal_id>/merge", methods=["POST"])
def merge_proposal(proposal_id: str):
    """Merge an approved proposal to main."""
    Proposal = _get_proposal_model()
    ApprovalEvent, _ = _get_approval_models()
    db = _get_db()
    _, merge_branch_to_main = _get_git_ops()
    agent_store = _get_agent_store()
    
    proposal = Proposal.query.get_or_404(proposal_id)
    
    if proposal.status != "APPROVED":
        flash("Proposal must be APPROVED before merge.", "danger")
        return redirect(url_for("admin_proposals.view_proposal", proposal_id=proposal_id))
    
    override = request.form.get("override", "") == "true"
    rationale = request.form.get("rationale", "").strip()
    
    risk_tier = _get_risk_tier(proposal.overall_risk)
    
    if risk_tier == "HIGH" and not override:
        flash("HIGH risk proposal requires explicit override confirmation.", "danger")
        return redirect(url_for("admin_proposals.view_proposal", proposal_id=proposal_id))
    
    if risk_tier == "HIGH" and not rationale:
        flash("HIGH risk merge requires a rationale.", "danger")
        return redirect(url_for("admin_proposals.view_proposal", proposal_id=proposal_id))
    
    try:
        merge_branch_to_main(proposal.branch, push=False)
        agent_store.mark_status(proposal_id, "MERGED")
        
        db.session.add(ApprovalEvent(
            proposal_id=str(proposal.id),
            actor_email=current_user.email or "unknown",
            action="MERGE",
            rationale=rationale
        ))
        db.session.commit()
        
        flash("Proposal merged to main successfully.", "success")
    except Exception as e:
        flash(f"Merge failed: {e}", "danger")
        logger.error(f"Merge failed for proposal {proposal_id}: {e}")
    
    return redirect(url_for("admin_proposals.view_proposal", proposal_id=proposal_id))


@admin_proposals_bp.route("/<proposal_id>/run-tests", methods=["POST"])
def run_tests(proposal_id: str):
    """Run tests for a proposal in sandbox."""
    Proposal = _get_proposal_model()
    
    proposal = Proposal.query.get_or_404(proposal_id)
    
    try:
        from services.sandbox import run_tests_in_sandbox
        passed, report = run_tests_in_sandbox(".", proposal.branch)
        
        if passed:
            flash("Tests passed!", "success")
        else:
            flash(f"Tests failed: {report[:200]}...", "danger")
    except Exception as e:
        flash(f"Failed to run tests: {e}", "danger")
        logger.error(f"Test run failed for proposal {proposal_id}: {e}")
    
    return redirect(url_for("admin_proposals.view_proposal", proposal_id=proposal_id))


def _get_agent_analysis_context():
    """Gather context about agent performance for proposal generation."""
    context = []
    try:
        from models import Finding, AgentStatus
        from sqlalchemy import func
        from datetime import datetime, timedelta
        
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)
        
        agent_stats = (AgentStatus.query
            .order_by(AgentStatus.last_run.desc())
            .limit(20)
            .all())
        
        for agent in agent_stats:
            recent_findings = (Finding.query
                .filter_by(agent_name=agent.agent_name)
                .filter(Finding.created_at >= week_ago)
                .count())
            
            context.append(f"Agent: {agent.agent_name}")
            context.append(f"  Status: {agent.status}, Last Run: {agent.last_run}")
            context.append(f"  Recent Findings (7d): {recent_findings}")
            context.append(f"  Run Count: {agent.run_count}, Error Count: {agent.error_count}")
            if agent.error_count > 0 and agent.run_count > 0:
                error_rate = agent.error_count / agent.run_count * 100
                context.append(f"  Error Rate: {error_rate:.1f}%")
            context.append("")
    except Exception as e:
        context.append(f"Could not gather agent stats: {e}")
    
    return "\n".join(context)


@admin_proposals_bp.route("/generate", methods=["POST"])
def generate_proposal():
    """Generate a new code proposal using the Builder Agent."""
    import uuid
    
    agent_store = _get_agent_store()
    proposal_type = request.form.get("type", "improvement")
    
    try:
        from agents.builder_agent import BuilderAgent
        
        builder = BuilderAgent()
        
        agent_context = _get_agent_analysis_context()
        
        if proposal_type == "fix_agent":
            task_description = f"""
            AGENT PERFORMANCE DATA:
            {agent_context}
            
            Analyze the agents with high error rates or low finding counts.
            Propose a FIX for the worst-performing agent:
            1. Identify the root cause of failures
            2. Write the actual code fix with proper error handling
            3. Include defensive coding practices
            """
        elif proposal_type == "new_agent":
            task_description = """
            Review the current agent ecosystem and propose a NEW AGENT:
            1. Identify market inefficiency gaps not covered by existing agents
            2. Propose a new agent that would add alpha
            3. Write the complete agent code following the BaseAgent pattern
            4. Include proper data fetching, analysis, and finding generation
            
            Suggested new agent types:
            - Options flow analysis agent
            - Earnings surprise detector
            - Sector rotation signal agent
            - Credit spread monitor
            - Insider trading tracker
            """
        else:
            task_description = f"""
            AGENT PERFORMANCE DATA:
            {agent_context}
            
            Review the current agent performance and propose one improvement:
            1. Look at agents with high error rates or low output
            2. Identify patterns in failures or missed opportunities
            3. Propose a small, safe enhancement to improve signal quality
            
            Focus on:
            - Improving confidence calibration
            - Adding validation checks
            - Better error handling
            - Data normalization improvements
            """
        
        proposal_data = builder.propose_change(task_description)
        
        if "blocking_reason" in proposal_data and "patch" not in proposal_data:
            flash(f"Builder agent blocked: {proposal_data.get('blocking_reason', 'Unknown reason')}", "warning")
            return redirect(url_for("admin_proposals.list_proposals"))
        
        pid = str(uuid.uuid4())[:12]
        branch_name = builder.generate_branch_name(proposal_data.get("title", "improvement"))
        
        diff_text = proposal_data.get("patch", "")
        if not diff_text:
            diff_text = f"# Proposal: {proposal_data.get('title', 'Untitled')}\n\n{proposal_data.get('summary', 'No summary')}"
        
        risk_notes = proposal_data.get("risk_notes", [])
        if isinstance(risk_notes, list):
            risk_notes = "\n".join(f"- {note}" for note in risk_notes)
        overall_risk = 0.3
        if "high" in str(risk_notes).lower():
            overall_risk = 0.7
        elif "low" in str(risk_notes).lower():
            overall_risk = 0.15
        
        agent_store.store_proposal(
            pid=pid,
            branch=branch_name,
            title=proposal_data.get("title", "AI Generated Improvement"),
            summary=proposal_data.get("summary", "Auto-generated proposal"),
            rationale=str(risk_notes),
            unified_diff=diff_text,
            overall_risk=overall_risk,
            file_risk={}
        )
        
        flash(f"Generated proposal: {proposal_data.get('title', 'New Proposal')}", "success")
        return redirect(url_for("admin_proposals.view_proposal", proposal_id=pid))
        
    except Exception as e:
        logger.error(f"Failed to generate proposal: {e}")
        flash(f"Failed to generate proposal: {str(e)}", "danger")
        return redirect(url_for("admin_proposals.list_proposals"))


def _is_safe_path(file_path: str, base_dir: str = ".") -> bool:
    """Check if file path is safe (no path traversal attacks)."""
    import os
    if not file_path:
        return False
    if file_path == "/dev/null":
        return False
    abs_base = os.path.abspath(base_dir)
    abs_path = os.path.abspath(os.path.join(base_dir, file_path))
    return abs_path.startswith(abs_base + os.sep) or abs_path == abs_base


def _normalize_diff_path(path: str) -> str:
    """Normalize and clean a path from a diff header."""
    path = path.strip()
    for prefix in ['+++ b/', '+++ a/', '+++ ', '--- b/', '--- a/', '--- ']:
        if path.startswith(prefix):
            path = path[len(prefix):]
            break
    return path.strip()


@admin_proposals_bp.route("/<proposal_id>/apply", methods=["POST"])
def apply_proposal(proposal_id: str):
    """Apply a proposal's code changes directly to the codebase."""
    import os
    import re
    
    Proposal = _get_proposal_model()
    ApprovalEvent, _ = _get_approval_models()
    db = _get_db()
    agent_store = _get_agent_store()
    
    proposal = Proposal.query.get_or_404(proposal_id)
    
    allowed_statuses = ["APPROVED", "PENDING", "PROPOSED"]
    if proposal.status not in allowed_statuses:
        flash(f"Only {', '.join(allowed_statuses)} proposals can be applied.", "danger")
        return redirect(url_for("admin_proposals.view_proposal", proposal_id=proposal_id))
    
    diff_text = proposal.unified_diff or ""
    
    hunk_pattern = re.compile(r'^@@\s+-(\d+)(?:,\d+)?\s+\+(\d+)(?:,\d+)?\s+@@', re.MULTILINE)
    
    try:
        files_modified = []
        current_file = None
        new_content_lines = []
        
        lines = diff_text.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i]
            
            if line.startswith('--- '):
                pass
            elif line.startswith('+++ '):
                raw_path = _normalize_diff_path(line)
                
                if not raw_path or raw_path == '/dev/null':
                    current_file = None
                elif not _is_safe_path(raw_path):
                    logger.warning(f"Rejected unsafe path in diff: {raw_path}")
                    flash(f"Rejected unsafe file path: {raw_path}", "danger")
                    current_file = None
                else:
                    current_file = raw_path
                    if os.path.exists(current_file):
                        with open(current_file, 'r') as f:
                            new_content_lines = f.readlines()
                    else:
                        new_content_lines = []
                        dir_name = os.path.dirname(current_file)
                        if dir_name and _is_safe_path(dir_name):
                            os.makedirs(dir_name, exist_ok=True)
                            
            elif line.startswith('@@') and current_file:
                match = hunk_pattern.match(line)
                if match:
                    start_line = int(match.group(2)) - 1
                    i += 1
                    while i < len(lines) and not lines[i].startswith('@@') and not lines[i].startswith('diff '):
                        hunk_line = lines[i]
                        if hunk_line.startswith('+') and not hunk_line.startswith('+++'):
                            new_content_lines.insert(start_line, hunk_line[1:] + '\n')
                            start_line += 1
                        elif hunk_line.startswith('-') and not hunk_line.startswith('---'):
                            if start_line < len(new_content_lines):
                                new_content_lines.pop(start_line)
                        elif hunk_line.startswith(' ') or not hunk_line.startswith(('+', '-')):
                            start_line += 1
                        i += 1
                    i -= 1
                    
                    with open(current_file, 'w') as f:
                        f.writelines(new_content_lines)
                    if current_file not in files_modified:
                        files_modified.append(current_file)
            i += 1
        
        if files_modified:
            agent_store.mark_status(proposal_id, "APPLIED")
            
            db.session.add(ApprovalEvent(
                proposal_id=str(proposal.id),
                actor_email=current_user.email or "unknown",
                action="APPLY",
                rationale=f"Applied changes to: {', '.join(files_modified)}"
            ))
            db.session.commit()
            
            flash(f"Successfully applied changes to {len(files_modified)} file(s): {', '.join(files_modified)}", "success")
        else:
            flash("No file changes could be extracted from the diff. The proposal may need manual application.", "warning")
        
    except Exception as e:
        logger.error(f"Failed to apply proposal {proposal_id}: {e}")
        flash(f"Failed to apply proposal: {str(e)}", "danger")
    
    return redirect(url_for("admin_proposals.view_proposal", proposal_id=proposal_id))
