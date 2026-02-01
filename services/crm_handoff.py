"""
CRM / Deal Room Handoff Service

Handles syncing deals to external CRM systems and deal rooms.
Supports webhooks for real-time updates on ACT recommendations.
"""
import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

import requests

logger = logging.getLogger(__name__)


@dataclass
class CRMConfig:
    """CRM integration configuration."""
    name: str
    webhook_url: str
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    enabled: bool = True
    sync_stages: List[str] = None
    
    def __post_init__(self):
        if self.sync_stages is None:
            self.sync_stages = ["underwritten", "loi", "closed"]


def load_crm_configs() -> List[CRMConfig]:
    """Load CRM configurations from environment."""
    configs = []
    
    webhook_url = os.getenv("CRM_WEBHOOK_URL")
    if webhook_url:
        configs.append(CRMConfig(
            name=os.getenv("CRM_NAME", "DefaultCRM"),
            webhook_url=webhook_url,
            api_key=os.getenv("CRM_API_KEY"),
            api_secret=os.getenv("CRM_API_SECRET"),
            enabled=os.getenv("CRM_ENABLED", "true").lower() == "true",
            sync_stages=os.getenv("CRM_SYNC_STAGES", "underwritten,loi,closed").split(",")
        ))
    
    deal_room_url = os.getenv("DEAL_ROOM_WEBHOOK_URL")
    if deal_room_url:
        configs.append(CRMConfig(
            name=os.getenv("DEAL_ROOM_NAME", "DealRoom"),
            webhook_url=deal_room_url,
            api_key=os.getenv("DEAL_ROOM_API_KEY"),
            enabled=os.getenv("DEAL_ROOM_ENABLED", "true").lower() == "true",
            sync_stages=["loi", "closed"]
        ))
    
    i = 1
    while True:
        url = os.getenv(f"CRM_{i}_WEBHOOK_URL")
        if not url:
            break
        configs.append(CRMConfig(
            name=os.getenv(f"CRM_{i}_NAME", f"CRM_{i}"),
            webhook_url=url,
            api_key=os.getenv(f"CRM_{i}_API_KEY"),
            enabled=os.getenv(f"CRM_{i}_ENABLED", "true").lower() == "true"
        ))
        i += 1
    
    return [c for c in configs if c.enabled]


def sync_deal_to_crm(deal_id: int, trigger: str = "manual") -> Dict[str, Any]:
    """
    Sync a deal to all configured CRM systems.
    
    Args:
        deal_id: Database ID of the deal
        trigger: What triggered the sync (manual, stage_change, act_recommendation)
    
    Returns:
        Sync result with status for each CRM
    """
    from models import DistressedDeal, db
    
    deal = DistressedDeal.query.get(deal_id)
    if not deal:
        return {"success": False, "error": "Deal not found", "synced": []}
    
    configs = load_crm_configs()
    if not configs:
        return {"success": True, "message": "No CRM configured", "synced": []}
    
    results = []
    
    for config in configs:
        if deal.stage not in config.sync_stages:
            results.append({
                "crm": config.name,
                "synced": False,
                "reason": f"Stage {deal.stage} not in sync stages"
            })
            continue
        
        payload = _build_crm_payload(deal, trigger)
        
        try:
            response = _send_to_crm(config, payload)
            
            if response.get("success"):
                deal.crm_synced = True
                deal.crm_sync_at = datetime.utcnow()
                if response.get("external_id"):
                    deal.crm_external_id = response["external_id"]
                if response.get("deal_room_url"):
                    deal.deal_room_url = response["deal_room_url"]
                
                db.session.commit()
            
            results.append({
                "crm": config.name,
                "synced": response.get("success", False),
                "external_id": response.get("external_id"),
                "deal_room_url": response.get("deal_room_url")
            })
            
        except Exception as e:
            logger.error(f"CRM sync error for {config.name}: {e}")
            results.append({
                "crm": config.name,
                "synced": False,
                "error": str(e)
            })
    
    all_synced = all(r.get("synced") for r in results)
    
    return {
        "success": all_synced,
        "deal_id": deal_id,
        "trigger": trigger,
        "synced": results
    }


def _build_crm_payload(deal, trigger: str) -> Dict[str, Any]:
    """Build CRM-compatible payload from deal."""
    return {
        "source": "MarketInefficiencyPlatform",
        "trigger": trigger,
        "timestamp": datetime.utcnow().isoformat(),
        "deal": {
            "internal_id": deal.id,
            "property": {
                "address": deal.property_address,
                "city": deal.city,
                "state": deal.state,
                "zip": deal.zip_code,
                "type": deal.property_type,
                "distress_type": deal.distress_type
            },
            "financials": {
                "asking_price": deal.asking_price,
                "estimated_value": deal.estimated_value,
                "offer_price": deal.offer_price,
                "final_price": deal.final_price
            },
            "pipeline": {
                "stage": deal.stage,
                "stage_history": deal.stage_history,
                "assigned_to": deal.assigned_to
            },
            "analysis": {
                "ic_memo": deal.ic_memo,
                "underwriting_score": deal.underwriting_score,
                "source_agent": deal.source_agent,
                "finding_id": deal.finding_id
            },
            "metadata": deal.deal_metadata
        }
    }


def _send_to_crm(config: CRMConfig, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Send payload to CRM webhook."""
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "MarketInefficiencyPlatform/1.0"
    }
    
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    if config.api_secret:
        headers["X-API-Secret"] = config.api_secret
    
    try:
        response = requests.post(
            config.webhook_url,
            json=payload,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        
        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError) as e:
            logger.debug(f"Could not parse CRM response JSON: {e}")
            data = {}
        
        return {
            "success": True,
            "status_code": response.status_code,
            "external_id": data.get("id") or data.get("deal_id") or data.get("external_id"),
            "deal_room_url": data.get("deal_room_url") or data.get("url")
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(f"CRM webhook failed: {e}")
        return {"success": False, "error": str(e)}


def handle_act_recommendation(deal_id: int, recommendation: str) -> Dict[str, Any]:
    """
    Handle ACT recommendation from IC memo.
    Triggers CRM sync and deal room creation.
    
    Args:
        deal_id: Deal ID
        recommendation: ACT, WATCH, or PASS
    
    Returns:
        Action result
    """
    if recommendation.upper() != "ACT":
        return {"action": "none", "reason": f"Recommendation was {recommendation}"}
    
    from models import DistressedDeal, db
    
    deal = DistressedDeal.query.get(deal_id)
    if not deal:
        return {"action": "none", "error": "Deal not found"}
    
    if deal.stage == "screened":
        deal.progress_stage("underwritten", notes="Auto-progressed on ACT recommendation")
        db.session.commit()
    
    sync_result = sync_deal_to_crm(deal_id, trigger="act_recommendation")
    
    return {
        "action": "synced",
        "deal_id": deal_id,
        "new_stage": deal.stage,
        "sync_result": sync_result
    }


def create_deal_room(deal_id: int) -> Dict[str, Any]:
    """
    Create a deal room for a deal.
    
    In production, this would integrate with a deal room provider
    (e.g., Intralinks, Firmex, or custom solution).
    """
    from models import DistressedDeal, db
    
    deal = DistressedDeal.query.get(deal_id)
    if not deal:
        return {"success": False, "error": "Deal not found"}
    
    deal_room_url = os.getenv("DEAL_ROOM_BASE_URL", "/deals")
    deal.deal_room_url = f"{deal_room_url}/{deal_id}"
    db.session.commit()
    
    logger.info(f"Deal room created for deal {deal_id}: {deal.deal_room_url}")
    
    return {
        "success": True,
        "deal_id": deal_id,
        "deal_room_url": deal.deal_room_url
    }


def get_crm_status() -> Dict[str, Any]:
    """Get status of all CRM integrations."""
    configs = load_crm_configs()
    
    return {
        "configured": len(configs) > 0,
        "integrations": [
            {
                "name": c.name,
                "enabled": c.enabled,
                "sync_stages": c.sync_stages,
                "webhook_configured": bool(c.webhook_url)
            }
            for c in configs
        ]
    }
