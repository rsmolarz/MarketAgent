"""
Registry: Reads and writes agent_schedule.json for scheduler enforcement.
This is the bridge between Meta-Agent decisions and live scheduling.
"""
import json
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

SCHEDULE_PATH = Path("agent_schedule.json")  # Root level, matching scheduler.py expectations


def load_schedule() -> Dict[str, Dict]:
    """
    Loads the current agent schedule.
    Handles both formats:
    - Legacy: {"AgentName": 60} (just interval)
    - New: {"AgentName": {"enabled": true, "weight": 1.0, ...}}
    """
    if not SCHEDULE_PATH.exists():
        return {}
    
    try:
        data = json.loads(SCHEDULE_PATH.read_text())
        # Normalize to new format
        result = {}
        for agent, value in data.items():
            if isinstance(value, (int, float)):
                # Legacy format - convert to new format
                result[agent] = {
                    "interval": int(value),
                    "enabled": True,
                    "weight": 1.0,
                    "reason": "legacy",
                }
            else:
                result[agent] = value
        return result
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Error loading schedule: {e}")
        return {}


def save_schedule(schedule: Dict[str, Dict]) -> None:
    """
    Saves the agent schedule to disk.
    """
    SCHEDULE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCHEDULE_PATH.write_text(json.dumps(schedule, indent=2))
    logger.info(f"Saved schedule to {SCHEDULE_PATH}")


def update_schedule(decisions: Dict[str, Dict]) -> Dict[str, Dict]:
    """
    Updates agent_schedule.json with Meta-Agent decisions.
    Preserves existing fields (like interval) while updating meta-agent fields.
    
    Args:
        decisions: Output from rank_agents()
    
    Returns:
        Updated schedule dict
    """
    schedule = load_schedule()
    
    for agent, d in decisions.items():
        if agent not in schedule:
            schedule[agent] = {"interval": 30}  # Default 30 min interval
        
        # Update meta-agent controlled fields
        schedule[agent]["enabled"] = d["enabled"]
        schedule[agent]["weight"] = d["weight"]
        schedule[agent]["reason"] = d["reason"]
        schedule[agent]["rank"] = d.get("rank")
        schedule[agent]["score"] = d.get("score", 0.0)
    
    save_schedule(schedule)
    return schedule


def sync_schedule_with_scheduler():
    """
    Syncs schedule decisions with running scheduler jobs.
    Call this after update_schedule to stop disabled agents.
    """
    try:
        from scheduler import scheduler as live_scheduler
        schedule = load_schedule()
        
        for agent, cfg in schedule.items():
            if not cfg.get("enabled", True):
                live_scheduler.stop_agent(agent)
                logger.info(f"Stopped disabled agent: {agent}")
    except ImportError:
        logger.warning("Could not import scheduler for sync")


def get_agent_config(agent_name: str) -> Dict[str, Any]:
    """
    Gets configuration for a specific agent.
    """
    schedule = load_schedule()
    return schedule.get(agent_name, {})


def is_agent_enabled(agent_name: str) -> bool:
    """
    Checks if an agent is enabled.
    Returns True if agent is not in schedule (default enabled).
    """
    cfg = get_agent_config(agent_name)
    return cfg.get("enabled", True)


def get_agent_weight(agent_name: str) -> float:
    """
    Gets the capital allocation weight for an agent.
    Returns 1.0 if not set (default equal weight).
    """
    cfg = get_agent_config(agent_name)
    return cfg.get("weight", 1.0)


def list_enabled_agents() -> Dict[str, Dict]:
    """
    Returns dict of all enabled agents and their configs.
    """
    schedule = load_schedule()
    return {k: v for k, v in schedule.items() if v.get("enabled", True)}


def list_disabled_agents() -> Dict[str, Dict]:
    """
    Returns dict of all disabled agents and their configs.
    """
    schedule = load_schedule()
    return {k: v for k, v in schedule.items() if not v.get("enabled", True)}
