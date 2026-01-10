"""
Contract clause extraction service.

Extracts key contract clauses like governing law, venue, and personal guarantees
from legal document text using pattern matching and NLP.
"""

import re
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def extract_clauses(text: str) -> Dict[str, Any]:
    """
    Extract key clauses from contract text.
    
    Args:
        text: The raw text content of a legal document
        
    Returns:
        Dict with extracted clauses:
        - governing_law: State/jurisdiction (str or None)
        - venue: Forum/venue location (str or None)
        - personal_guarantee: Whether a personal guarantee exists (bool)
    """
    result = {
        "governing_law": None,
        "venue": None,
        "personal_guarantee": False
    }
    
    result["governing_law"] = extract_governing_law(text)
    result["venue"] = extract_venue(text)
    result["personal_guarantee"] = detect_personal_guarantee(text)
    
    return result


def extract_governing_law(text: str) -> Optional[str]:
    """
    Extract the governing law jurisdiction from contract text.
    
    Patterns matched:
    - "governed by the laws of [State]"
    - "governed by [State] law"
    - "subject to the laws of [State]"
    """
    patterns = [
        r"governed\s+by\s+(?:the\s+)?laws?\s+of\s+(?:the\s+)?(?:State\s+of\s+)?([A-Z][a-zA-Z\s]+?)(?:\.|,|;|\s+without)",
        r"governed\s+by\s+([A-Z][a-zA-Z]+)\s+law",
        r"subject\s+to\s+(?:the\s+)?laws?\s+of\s+(?:the\s+)?(?:State\s+of\s+)?([A-Z][a-zA-Z\s]+?)(?:\.|,|;)",
        r"laws?\s+of\s+(?:the\s+)?(?:State\s+of\s+)?([A-Z][a-zA-Z\s]+?)\s+(?:shall\s+)?govern",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            state = match.group(1).strip()
            state = re.sub(r'\s+', ' ', state)
            if state.lower() not in ('the', 'a', 'an', 'this', 'such'):
                return state
    
    return None


def extract_venue(text: str) -> Optional[str]:
    """
    Extract the venue/forum selection clause from contract text.
    
    Patterns matched:
    - "Venue shall lie in [Location]"
    - "exclusive jurisdiction of the courts of [Location]"
    - "forum for any dispute shall be [Location]"
    """
    patterns = [
        r"[Vv]enue\s+(?:shall\s+)?(?:lie\s+)?(?:exclusively\s+)?in\s+([A-Z][a-zA-Z\s,]+?)(?:\.|;|$)",
        r"exclusive\s+(?:jurisdiction|venue)\s+(?:of\s+)?(?:the\s+)?(?:courts?\s+)?(?:of\s+|in\s+)?([A-Z][a-zA-Z\s,]+?)(?:\.|;|$)",
        r"forum\s+(?:for\s+)?(?:any\s+)?(?:dispute|action|proceeding)\s+shall\s+be\s+([A-Z][a-zA-Z\s,]+?)(?:\.|;|$)",
        r"courts?\s+(?:located\s+)?in\s+([A-Z][a-zA-Z\s,]+?)\s+shall\s+have\s+(?:exclusive\s+)?jurisdiction",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            venue = match.group(1).strip()
            venue = re.sub(r'\s+', ' ', venue)
            venue = venue.rstrip(',')
            if venue.lower() not in ('the', 'a', 'an', 'this', 'such'):
                return venue
    
    return None


def detect_personal_guarantee(text: str) -> bool:
    """
    Detect if the contract contains a personal guarantee clause.
    
    Patterns matched:
    - "personally guarantee(s)"
    - "personal guarantee"
    - "personally guaranteed by"
    - "undersigned personally guarantees"
    """
    patterns = [
        r"personal(?:ly)?\s+guarantee[sd]?",
        r"undersigned\s+(?:\w+\s+)?personal(?:ly)?\s+guarantee[sd]?",
        r"guarantee[sd]?\s+(?:all\s+)?obligations?\s+personal(?:ly)?",
        r"individual(?:ly)?\s+(?:and\s+)?personal(?:ly)?\s+(?:jointly\s+and\s+severally\s+)?(?:liable|guarantee)",
    ]
    
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    
    return False
