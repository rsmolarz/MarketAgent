"""
Deal Management Routes

Handles distressed property deal pipeline:
- Create deals from findings
- Progress through stages (screened → underwritten → LOI → closed)
- Generate IC memos
- CRM/deal room handoff
"""
import logging
from datetime import datetime
from flask import Blueprint, jsonify, request, render_template

from models import db, DistressedDeal, Finding, ICVote, DealValuation

logger = logging.getLogger(__name__)

deals_bp = Blueprint("deals", __name__, url_prefix="/deals")


@deals_bp.route("/")
def deal_list():
    """List all deals with pipeline view."""
    stage = request.args.get("stage")
    
    query = DistressedDeal.query.order_by(DistressedDeal.updated_at.desc())
    
    if stage:
        query = query.filter(DistressedDeal.stage == stage)
    
    deals = query.limit(100).all()
    
    pipeline = {
        "screened": [],
        "underwritten": [],
        "loi": [],
        "closed": [],
        "dead": []
    }
    
    for deal in deals:
        pipeline[deal.stage].append(deal.to_dict())
    
    if request.headers.get("Accept") == "application/json":
        return jsonify({
            "deals": [d.to_dict() for d in deals],
            "pipeline": pipeline,
            "counts": {k: len(v) for k, v in pipeline.items()}
        })
    
    return render_template(
        "deals.html",
        deals=deals,
        pipeline=pipeline,
        counts={k: len(v) for k, v in pipeline.items()}
    )


@deals_bp.route("/api/list")
def deal_list_api():
    """API endpoint for deal list."""
    stage = request.args.get("stage")
    limit = request.args.get("limit", 50, type=int)
    
    query = DistressedDeal.query.order_by(DistressedDeal.updated_at.desc())
    
    if stage:
        query = query.filter(DistressedDeal.stage == stage)
    
    deals = query.limit(limit).all()
    
    return jsonify({
        "success": True,
        "deals": [d.to_dict() for d in deals],
        "count": len(deals)
    })


@deals_bp.route("/api/pipeline")
def deal_pipeline_api():
    """Get deal pipeline summary."""
    stages = ["screened", "underwritten", "loi", "closed", "dead"]
    
    pipeline = {}
    for stage in stages:
        count = DistressedDeal.query.filter(DistressedDeal.stage == stage).count()
        pipeline[stage] = count
    
    total_value = db.session.query(
        db.func.sum(DistressedDeal.asking_price)
    ).filter(DistressedDeal.stage.in_(["screened", "underwritten", "loi"])).scalar() or 0
    
    closed_value = db.session.query(
        db.func.sum(DistressedDeal.final_price)
    ).filter(DistressedDeal.stage == "closed").scalar() or 0
    
    return jsonify({
        "success": True,
        "pipeline": pipeline,
        "total_active_value": total_value,
        "total_closed_value": closed_value
    })


@deals_bp.route("/<int:deal_id>")
def deal_detail(deal_id: int):
    """Get deal details."""
    deal = DistressedDeal.query.get_or_404(deal_id)
    
    if request.headers.get("Accept") == "application/json":
        return jsonify(deal.to_dict())
    
    return render_template("deal_detail.html", deal=deal)


@deals_bp.route("/create", methods=["POST"])
def create_deal():
    """Create a new deal."""
    data = request.json or {}
    
    address = data.get("property_address") or data.get("address")
    if not address:
        return jsonify({"success": False, "error": "property_address required"}), 400
    
    deal = DistressedDeal(
        property_address=address,
        city=data.get("city"),
        state=data.get("state"),
        zip_code=data.get("zip_code"),
        property_type=data.get("property_type"),
        distress_type=data.get("distress_type", "unknown"),
        asking_price=data.get("asking_price") or data.get("price"),
        estimated_value=data.get("estimated_value"),
        stage="screened",
        finding_id=data.get("finding_id"),
        source_agent=data.get("source_agent", "Manual"),
        deal_metadata=data.get("metadata")
    )
    
    db.session.add(deal)
    db.session.commit()
    
    logger.info(f"Created deal {deal.id}: {deal.property_address}")
    
    return jsonify({
        "success": True,
        "deal": deal.to_dict()
    })


@deals_bp.route("/from-finding/<int:finding_id>", methods=["POST"])
def create_from_finding(finding_id: int):
    """Create a deal from a finding."""
    finding = Finding.query.get_or_404(finding_id)
    
    metadata = finding.finding_metadata or {}
    
    deal = DistressedDeal(
        property_address=metadata.get("address", f"Property from Finding #{finding_id}"),
        city=metadata.get("city"),
        state=metadata.get("state"),
        zip_code=metadata.get("zip_code"),
        property_type=metadata.get("property_type"),
        distress_type=metadata.get("status", "unknown"),
        asking_price=metadata.get("price"),
        estimated_value=metadata.get("estimated_value") or metadata.get("market_value"),
        stage="screened",
        finding_id=finding_id,
        source_agent=finding.agent_name,
        deal_metadata={
            "finding_title": finding.title,
            "finding_description": finding.description,
            "finding_severity": finding.severity,
            "finding_confidence": finding.confidence,
            **metadata
        }
    )
    
    db.session.add(deal)
    db.session.commit()
    
    logger.info(f"Created deal {deal.id} from finding {finding_id}")
    
    return jsonify({
        "success": True,
        "deal": deal.to_dict()
    })


@deals_bp.route("/<int:deal_id>/progress", methods=["POST"])
def progress_deal(deal_id: int):
    """Progress a deal to the next stage."""
    deal = DistressedDeal.query.get_or_404(deal_id)
    
    data = request.json or {}
    new_stage = data.get("stage")
    notes = data.get("notes")
    
    if not new_stage:
        return jsonify({"success": False, "error": "stage required"}), 400
    
    old_stage = deal.stage
    success = deal.progress_stage(new_stage, notes)
    
    if not success:
        return jsonify({
            "success": False,
            "error": f"Cannot progress from {old_stage} to {new_stage}"
        }), 400
    
    if new_stage in ["underwritten", "loi", "closed"]:
        from services.crm_handoff import sync_deal_to_crm
        sync_result = sync_deal_to_crm(deal_id, trigger="stage_change")
    else:
        sync_result = None
    
    db.session.commit()
    
    logger.info(f"Deal {deal_id} progressed: {old_stage} → {new_stage}")
    
    return jsonify({
        "success": True,
        "deal": deal.to_dict(),
        "crm_sync": sync_result
    })


@deals_bp.route("/<int:deal_id>/generate-memo", methods=["POST"])
def generate_memo(deal_id: int):
    """Generate IC memo for a deal."""
    from services.distressed_ic_memo import generate_memo_for_deal, build_distressed_ic_memo
    from services.crm_handoff import handle_act_recommendation
    
    deal = DistressedDeal.query.get_or_404(deal_id)
    
    data = request.json or {}
    use_llm = data.get("use_llm", True)
    
    memo = generate_memo_for_deal(deal_id, use_llm=use_llm)
    
    if not memo:
        return jsonify({"success": False, "error": "Failed to generate memo"}), 500
    
    if memo.get("recommendation") == "ACT":
        act_result = handle_act_recommendation(deal_id, "ACT")
    else:
        act_result = None
    
    return jsonify({
        "success": True,
        "memo": memo,
        "act_handling": act_result
    })


@deals_bp.route("/<int:deal_id>/sync-crm", methods=["POST"])
def sync_crm(deal_id: int):
    """Manually sync deal to CRM."""
    from services.crm_handoff import sync_deal_to_crm
    
    deal = DistressedDeal.query.get_or_404(deal_id)
    
    result = sync_deal_to_crm(deal_id, trigger="manual")
    
    return jsonify({
        "success": result.get("success", False),
        "result": result
    })


@deals_bp.route("/<int:deal_id>/create-deal-room", methods=["POST"])
def create_deal_room_route(deal_id: int):
    """Create deal room for a deal."""
    from services.crm_handoff import create_deal_room
    
    deal = DistressedDeal.query.get_or_404(deal_id)
    
    result = create_deal_room(deal_id)
    
    return jsonify(result)


@deals_bp.route("/<int:deal_id>/update", methods=["PATCH", "PUT"])
def update_deal(deal_id: int):
    """Update deal fields."""
    deal = DistressedDeal.query.get_or_404(deal_id)
    
    data = request.json or {}
    
    updatable = [
        "offer_price", "final_price", "assigned_to",
        "underwriting_notes", "underwriting_score"
    ]
    
    for field in updatable:
        if field in data:
            setattr(deal, field, data[field])
    
    db.session.commit()
    
    return jsonify({
        "success": True,
        "deal": deal.to_dict()
    })


@deals_bp.route("/crm-status")
def crm_status():
    """Get CRM integration status."""
    from services.crm_handoff import get_crm_status
    
    return jsonify(get_crm_status())


@deals_bp.route("/<int:deal_id>/vote", methods=["POST"])
def add_ic_vote(deal_id: int):
    """Add an IC vote to a deal."""
    deal = DistressedDeal.query.get_or_404(deal_id)
    
    data = request.json or {}
    voter = data.get("voter")
    vote = data.get("vote")
    
    if not voter or not vote:
        return jsonify({"success": False, "error": "voter and vote required"}), 400
    
    if vote.upper() not in ["ACT", "WATCH", "PASS"]:
        return jsonify({"success": False, "error": "vote must be ACT, WATCH, or PASS"}), 400
    
    ai_vote = ICVote.query.filter_by(deal_id=deal_id, voter_type="ai").order_by(
        ICVote.created_at.desc()
    ).first()
    ai_vote_val = ai_vote.vote if ai_vote else None
    
    is_override = False
    override_reason = None
    
    voter_type = data.get("voter_type", "human")
    
    if voter_type == "human" and ai_vote_val:
        if vote.upper() != ai_vote_val.upper():
            is_override = True
            override_reason = f"Human override: AI voted {ai_vote_val}, human voted {vote.upper()}"
    
    ic_vote = ICVote(
        deal_id=deal_id,
        voter=voter,
        voter_type=voter_type,
        vote=vote.upper(),
        confidence=data.get("confidence"),
        notes=data.get("notes"),
        is_override=is_override,
        override_reason=override_reason
    )
    
    db.session.add(ic_vote)
    
    if voter_type == "human" and vote.upper() == "PASS":
        deal.progress_stage("dead", notes=f"IC PASS vote by {voter}")
    elif voter_type == "ai" and vote.upper() == "ACT" and deal.stage == "screened":
        pass
    
    db.session.commit()
    
    return jsonify({
        "success": True,
        "vote": ic_vote.to_dict(),
        "is_override": is_override
    })


@deals_bp.route("/<int:deal_id>/votes")
def get_ic_votes(deal_id: int):
    """Get all IC votes for a deal."""
    deal = DistressedDeal.query.get_or_404(deal_id)
    
    votes = ICVote.query.filter_by(deal_id=deal_id).order_by(ICVote.created_at.desc()).all()
    
    ai_votes = [v for v in votes if v.voter_type == "ai"]
    human_votes = [v for v in votes if v.voter_type == "human"]
    
    vote_counts = {"ACT": 0, "WATCH": 0, "PASS": 0}
    for v in human_votes:
        if v.vote in vote_counts:
            vote_counts[v.vote] += 1
    
    ai_recommendation = ai_votes[0].vote if ai_votes else None
    ai_confidence = ai_votes[0].confidence if ai_votes else None
    
    has_override = any(v.is_override for v in votes)
    
    return jsonify({
        "success": True,
        "votes": [v.to_dict() for v in votes],
        "summary": {
            "ai_recommendation": ai_recommendation,
            "ai_confidence": ai_confidence,
            "human_votes": vote_counts,
            "total_human": sum(vote_counts.values()),
            "has_override": has_override
        }
    })


@deals_bp.route("/api/exposure")
def deal_exposure_api():
    """Get portfolio-level exposure by deal stage."""
    from services.deal_kill_rules import get_deal_exposure_by_stage
    
    exposure = get_deal_exposure_by_stage()
    
    return jsonify({
        "success": True,
        **exposure
    })


@deals_bp.route("/<int:deal_id>/valuation", methods=["GET", "POST"])
def deal_valuation(deal_id: int):
    """Get or set deal valuation/pricing bands."""
    deal = DistressedDeal.query.get_or_404(deal_id)
    
    if request.method == "GET":
        valuation = DealValuation.query.get(deal_id)
        if valuation:
            return jsonify({"success": True, "valuation": valuation.to_dict()})
        return jsonify({"success": False, "error": "No valuation found"}), 404
    
    data = request.json or {}
    zestimate = data.get("zestimate")
    
    if not zestimate:
        return jsonify({"success": False, "error": "zestimate required"}), 400
    
    valuation = DealValuation.query.get(deal_id)
    if not valuation:
        valuation = DealValuation(deal_id=deal_id)
        db.session.add(valuation)
    
    valuation.zestimate = zestimate
    valuation.rent_zestimate = data.get("rent_zestimate")
    valuation.valuation_source = data.get("source", "manual")
    
    discount_low = data.get("discount_low", 0.55)
    discount_high = data.get("discount_high", 0.75)
    valuation.compute_pricing_bands(zestimate, discount_low, discount_high)
    
    valuation.confidence = data.get("confidence")
    
    db.session.commit()
    
    return jsonify({
        "success": True,
        "valuation": valuation.to_dict()
    })


@deals_bp.route("/api/kill-sweep", methods=["POST"])
def run_kill_sweep():
    """Run the deal kill sweep (admin only)."""
    from services.deal_kill_rules import run_deal_kill_sweep
    
    try:
        result = run_deal_kill_sweep()
        return jsonify({"success": True, **result})
    except Exception as e:
        logger.exception(f"Kill sweep failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
