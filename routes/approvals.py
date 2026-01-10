import json
import os
from pathlib import Path
from datetime import datetime, timezone
from flask import Blueprint, request, session, redirect, url_for, render_template, abort

approvals_bp = Blueprint("approvals", __name__)

META_REPORT = Path("meta_supervisor/reports/meta_report.json")
PROPOSALS_A = Path("meta_supervisor/agent_proposals.json")
PROPOSALS_R = Path("meta_supervisor/agent_proposals_regime.json")

STATE_DIR = Path("meta_supervisor/state")
APPROVALS_STATE = STATE_DIR / "approvals_state.json"
IC_STATE = STATE_DIR / "ic_checklists.json"
EXPLAIN_STATE = STATE_DIR / "proposal_explainers.json"
PROMO_STATE = STATE_DIR / "promotion_approvals.json"

def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def _load_json(path: Path, default):
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text())
    except Exception:
        return default

def _save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))

def _admin_token_required():
    token = os.environ.get("ADMIN_DASH_TOKEN", "")
    if not token:
        return True
    provided = request.args.get("token") or request.headers.get("X-Admin-Token") or session.get("admin_token")
    return provided == token

def _require_admin():
    if not _admin_token_required():
        abort(403)

def _approvers():
    raw = os.environ.get("PROMOTION_APPROVERS", "")
    return [x.strip().lower() for x in raw.split(",") if x.strip()]

def _threshold():
    try:
        return int(os.environ.get("PROMOTION_THRESHOLD", "2"))
    except Exception:
        return 2

def _github_cfg():
    return {
        "token": os.environ.get("GITHUB_TOKEN"),
        "repo": os.environ.get("GITHUB_REPO"),
    }

def _list_open_prs():
    cfg = _github_cfg()
    if not cfg["token"] or not cfg["repo"]:
        return []

    import urllib.request

    url = f"https://api.github.com/repos/{cfg['repo']}/pulls?state=open&per_page=20"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {cfg['token']}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "MarketAgent-Approvals",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []

    prs = []
    for pr in data:
        prs.append({
            "number": pr.get("number"),
            "title": pr.get("title"),
            "url": pr.get("html_url"),
            "user": (pr.get("user") or {}).get("login"),
            "updated_at": pr.get("updated_at"),
        })
    return prs

def _all_proposals():
    a = _load_json(PROPOSALS_A, {"proposals": []}).get("proposals", [])
    r = _load_json(PROPOSALS_R, {"proposals": []}).get("proposals", [])
    def norm(p, source):
        p = dict(p)
        p.setdefault("id", p.get("name"))
        p.setdefault("source", source)
        p.setdefault("status", "PENDING")
        p.setdefault("created_at", _now())
        return p
    out = [norm(p, "manual") for p in a] + [norm(p, "regime") for p in r]
    return out

def _save_proposals(updated):
    manual = [p for p in updated if p.get("source") == "manual"]
    regime = [p for p in updated if p.get("source") == "regime"]
    _save_json(PROPOSALS_A, {"proposals": manual})
    _save_json(PROPOSALS_R, {"proposals": regime})

def _ic_template():
    return {
        "data_sources_validated": False,
        "eval_plan_defined": False,
        "risk_controls_defined": False,
        "execution_guardrails": False,
        "shadow_mode_first": False,
        "owner_assigned": False,
    }

@approvals_bp.route("/admin/approvals/login", methods=["GET", "POST"])
def login():
    token = os.environ.get("ADMIN_DASH_TOKEN", "")
    if not token:
        return redirect(url_for("approvals.dashboard"))
    if request.method == "POST":
        provided = request.form.get("token", "")
        if provided == token:
            session["admin_token"] = provided
            return redirect(url_for("approvals.dashboard"))
        return render_template("approvals_login.html", error="Invalid token")
    return render_template("approvals_login.html", error=None)

@approvals_bp.route("/admin/approvals")
def dashboard():
    _require_admin()

    report = _load_json(META_REPORT, {})
    proposals = _all_proposals()
    ic = _load_json(IC_STATE, {})
    explainers = _load_json(EXPLAIN_STATE, {})
    promos = _load_json(PROMO_STATE, {})

    open_prs = _list_open_prs()

    agents = (report.get("agents") or {})
    promote_candidates = [a for a, s in agents.items() if s.get("decision") == "PROMOTE"]

    return render_template(
        "approvals_dashboard.html",
        report=report,
        open_prs=open_prs,
        proposals=proposals,
        ic=ic,
        explainers=explainers,
        promote_candidates=promote_candidates,
        promos=promos,
        approvers=_approvers(),
        threshold=_threshold(),
        now=_now(),
    )

@approvals_bp.route("/admin/approvals/proposal/<pid>/checklist", methods=["POST"])
def update_checklist(pid):
    _require_admin()
    ic = _load_json(IC_STATE, {})
    cur = ic.get(pid) or _ic_template()
    for k in cur.keys():
        cur[k] = bool(request.form.get(k))
    ic[pid] = cur
    _save_json(IC_STATE, ic)
    return redirect(url_for("approvals.dashboard"))

@approvals_bp.route("/admin/approvals/proposal/<pid>/set_status", methods=["POST"])
def set_proposal_status(pid):
    _require_admin()
    status = request.form.get("status", "PENDING").upper()
    proposals = _all_proposals()

    ic = _load_json(IC_STATE, {})
    checklist = ic.get(pid) or _ic_template()
    ic_complete = all(bool(v) for v in checklist.values())

    for p in proposals:
        if (p.get("id") == pid) or (p.get("name") == pid):
            if status == "APPROVED" and not ic_complete:
                p["status"] = "PENDING"
                p["status_note"] = "IC checklist incomplete"
            else:
                p["status"] = status
                p["status_note"] = ""
                p["updated_at"] = _now()
    _save_proposals(proposals)
    return redirect(url_for("approvals.dashboard"))

@approvals_bp.route("/admin/approvals/promotion/<agent>/sign", methods=["POST"])
def sign_promotion(agent):
    _require_admin()
    email = (request.form.get("email") or "").strip().lower()
    if not email:
        return redirect(url_for("approvals.dashboard"))

    allowed = set(_approvers())
    if allowed and email not in allowed:
        return redirect(url_for("approvals.dashboard"))

    promos = _load_json(PROMO_STATE, {})
    rec = promos.get(agent) or {"agent": agent, "signers": [], "created_at": _now()}
    if email not in rec["signers"]:
        rec["signers"].append(email)
    rec["updated_at"] = _now()
    promos[agent] = rec
    _save_json(PROMO_STATE, promos)
    return redirect(url_for("approvals.dashboard"))

@approvals_bp.route("/admin/approvals/promotion/<agent>/clear", methods=["POST"])
def clear_promotion(agent):
    _require_admin()
    promos = _load_json(PROMO_STATE, {})
    if agent in promos:
        del promos[agent]
        _save_json(PROMO_STATE, promos)
    return redirect(url_for("approvals.dashboard"))

@approvals_bp.route("/admin/approvals/proposal/<pid>/generate_explainer", methods=["POST"])
def generate_explainer(pid):
    _require_admin()
    report = _load_json(META_REPORT, {})
    proposals = _all_proposals()
    target = None
    for p in proposals:
        if (p.get("id") == pid) or (p.get("name") == pid):
            target = p
            break
    if not target:
        # Create a minimal target from the pid for manual/regime proposals
        target = {"id": pid, "name": pid, "strategy": "", "regime_trigger": ""}

    try:
        from openai import OpenAI
        key = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        base = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
        model = os.environ.get("PROPOSAL_EXPLAIN_MODEL", "gpt-4.1-mini")
        
        if not key:
            explainers = _load_json(EXPLAIN_STATE, {})
            explainers[pid] = {"updated_at": _now(), "markdown": "*Error: No OpenAI API key configured.*"}
            _save_json(EXPLAIN_STATE, explainers)
            return redirect(url_for("approvals.dashboard"))
        
        client = OpenAI(api_key=key, base_url=base) if base else OpenAI(api_key=key)

        prompt = {
            "proposal": target,
            "fleet": report.get("fleet", {}),
            "strategy_cvar": report.get("strategy_cvar", {}),
            "recent_decisions": {
                "promote": [a for a, s in (report.get("agents") or {}).items() if s.get("decision") == "PROMOTE"],
                "kill": [a for a, s in (report.get("agents") or {}).items() if s.get("decision") in ("KILL", "RETIRE")],
            },
        }

        msg = (
            "Explain why this agent was proposed, in PM language.\n"
            "Include: regime fit, edge hypothesis, key signals, risks, how it complements existing agents, and eval plan.\n"
            "Output markdown. Be specific to the JSON.\n\n"
            f"{json.dumps(prompt, indent=2)}"
        )

        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": "Output markdown only."},
                      {"role": "user", "content": msg}],
            temperature=0.2,
            max_tokens=900,
        )
        explainer_md = resp.choices[0].message.content

        explainers = _load_json(EXPLAIN_STATE, {})
        explainers[pid] = {"updated_at": _now(), "markdown": explainer_md}
        _save_json(EXPLAIN_STATE, explainers)
    except Exception as e:
        explainers = _load_json(EXPLAIN_STATE, {})
        explainers[pid] = {"updated_at": _now(), "markdown": f"*Error generating explainer: {str(e)}*"}
        _save_json(EXPLAIN_STATE, explainers)

    return redirect(url_for("approvals.dashboard"))


def promotion_is_approved(agent: str) -> bool:
    approvers = [x.strip().lower() for x in os.environ.get("PROMOTION_APPROVERS","").split(",") if x.strip()]
    threshold = int(os.environ.get("PROMOTION_THRESHOLD","2"))
    if not PROMO_STATE.exists():
        return False
    data = json.loads(PROMO_STATE.read_text())
    rec = data.get(agent) or {}
    signers = [s.lower() for s in (rec.get("signers") or [])]
    signers = list(dict.fromkeys(signers))
    if approvers:
        signers = [s for s in signers if s in approvers]
    return len(signers) >= threshold
