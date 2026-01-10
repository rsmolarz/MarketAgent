"""
Global Uncertainty State

Single source of truth for regime uncertainty.
Downstream consumers (email, dashboard, API) read from here.
"""

from datetime import datetime
from typing import Optional


class UncertaintyState:
    """
    Global uncertainty state singleton.
    
    When active, all signals are marked as provisional.
    No agent modification required - this is metadata-only.
    """
    active: bool = False
    last_update: Optional[datetime] = None
    entropy: float = 0.0
    prob_var: float = 0.0
    vote_split: int = 0
    source: str = "unknown"

    @classmethod
    def set_uncertainty(
        cls,
        active: bool,
        entropy: float = 0.0,
        prob_var: float = 0.0,
        vote_split: int = 0,
        source: str = "regime_council"
    ):
        """Update uncertainty state from regime council or detector."""
        cls.active = active
        cls.entropy = entropy
        cls.prob_var = prob_var
        cls.vote_split = vote_split
        cls.source = source
        cls.last_update = datetime.utcnow()

    @classmethod
    def banner(cls) -> Optional[str]:
        """Get warning banner if uncertainty is active."""
        if not cls.active:
            return None
        return "⚠️ REGIME UNCERTAINTY: Signals are provisional"

    @classmethod
    def to_dict(cls) -> dict:
        """Export state for API/logging."""
        return {
            "active": cls.active,
            "last_update": cls.last_update.isoformat() if cls.last_update else None,
            "entropy": cls.entropy,
            "prob_var": cls.prob_var,
            "vote_split": cls.vote_split,
            "source": cls.source,
            "banner": cls.banner()
        }


def annotate_finding(finding: dict) -> dict:
    """
    Attach uncertainty metadata to a finding.
    
    Call this once, centrally, where findings are saved.
    Result:
    - API: { provisional: true }
    - Dashboard: yellow banner
    - Emails: prepend warning
    """
    banner = UncertaintyState.banner()
    if banner:
        finding["provisional"] = True
        finding["disclaimer"] = banner
        finding["uncertainty_state"] = {
            "entropy": UncertaintyState.entropy,
            "prob_var": UncertaintyState.prob_var,
            "vote_split": UncertaintyState.vote_split,
        }
    else:
        finding["provisional"] = False
    return finding
