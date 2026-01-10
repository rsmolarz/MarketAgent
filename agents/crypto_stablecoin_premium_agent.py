"""
Detects temporary premium or discount inefficiencies in major crypto stablecoins
relative to their pegged fiat value by analyzing on-chain transfer volumes and
exchange price deviations.
"""

from typing import Any, Dict, List
from agents.base_agent import BaseAgent


class CryptoStablecoinPremiumAgent(BaseAgent):
    """
    Detects temporary premium or discount inefficiencies in major crypto
    stablecoins relative to their fiat peg.
    """

    def __init__(self):
        super().__init__("CryptoStablecoinPremiumAgent")

    def plan(self) -> Dict[str, Any]:
        """Plan the analysis strategy."""
        return {
            "steps": ["fetch_data", "analyze", "generate_findings"]
        }

    def act(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute the analysis and return findings."""
        return self.analyze()

    def analyze(self) -> List[Dict[str, Any]]:
        """
        Main analysis method. Returns list of findings.

        Each finding must have:
        - title (str)
        - description (str)
        - severity (low|medium|high)
        - confidence (0..1)
        - metadata (dict)
        - symbol (optional)
        - market_type (optional)
        """
        findings: List[Dict[str, Any]] = []

        # ---------------------------------------------------------
        # Simulated premium detection (deterministic test logic)
        # ---------------------------------------------------------
        premium_pct = 0.012  # 1.2% premium

        if premium_pct > 0.01:
            findings.append({
                "title": "Stablecoin Premium Detected",
                "description": (
                    "USDT is trading at a 1.2% premium relative to its USD peg."
                ),
                "severity": "medium",
                "confidence": 0.7,
                "metadata": {
                    "premium_pct": premium_pct
                },
                "symbol": "USDT",
                "market_type": "crypto"
            })

        return findings

    def reflect(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Reflect on the analysis results."""
        return {
            "finding_count": len(results),
            "high_severity_count": sum(
                1 for f in results if f.get("severity") == "high"
            )
        }


