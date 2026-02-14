import json
import os
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

FAILURES_FILE = Path("meta_supervisor/startup_failures.json")

def track_startup_failure(agent_name: str, error_message: str, error_details: str = ""):
    """Track agent startup failures for monitoring."""
    try:
        failures = []
        if FAILURES_FILE.exists():
            try:
                failures = json.loads(FAILURES_FILE.read_text())
            except:
                failures = []
        
        failure_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent_name": agent_name,
            "error_message": error_message,
            "error_details": error_details,
            "retry_count": 0,
            "last_seen": datetime.utcnow().isoformat()
        }
        
        existing = next((f for f in failures if f["agent_name"] == agent_name), None)
        if existing:
            existing["retry_count"] += 1
            existing["last_seen"] = failure_record["timestamp"]
            existing["error_message"] = error_message
        else:
            failures.append(failure_record)
        
        failures = sorted(failures, key=lambda x: x["timestamp"], reverse=True)[:100]
        
        FAILURES_FILE.parent.mkdir(parents=True, exist_ok=True)
        FAILURES_FILE.write_text(json.dumps(failures, indent=2))
        
        logger.warning(f"[StartupTracker] Recorded failure for {agent_name}: {error_message}")
    except Exception as e:
        logger.error(f"Failed to track startup failure: {e}")

def get_startup_failures():
    """Get all tracked startup failures."""
    try:
        if FAILURES_FILE.exists():
            return json.loads(FAILURES_FILE.read_text())
        return []
    except Exception as e:
        logger.error(f"Error reading startup failures: {e}")
        return []

def clear_startup_failures(agent_name: str = None):
    """Clear startup failures for a specific agent or all."""
    try:
        if not FAILURES_FILE.exists():
            return
        
        failures = json.loads(FAILURES_FILE.read_text())
        
        if agent_name:
            failures = [f for f in failures if f["agent_name"] != agent_name]
        else:
            failures = []
        
        FAILURES_FILE.write_text(json.dumps(failures, indent=2))
    except Exception as e:
        logger.error(f"Error clearing startup failures: {e}")
