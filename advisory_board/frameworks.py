"""
Analytical Frameworks for the Advisory Board

Implements structured analysis tools:
- BarbellAnalyzer: Corporate barbell strategy decomposition
- BlackSwanScanner: Tail-risk identification framework
- AlphaExtractor: Signal extraction and edge assessment
- ConvexityMapper: Maps payoff profiles for convexity/concavity
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class BarbellAnalyzer:
    """
    Applies Taleb's Barbell Strategy to corporate decisions.

    The barbell strategy allocates resources between two extremes:
    - SAFETY (85-90%): Ultra-conservative, indestructible base
    - UPSIDE (10-15%): High-risk, convex, asymmetric bets

    Nothing in the "middle" — the fragile zone where moderate risk
    yields moderate returns but exposure to ruin.
    """

    SAFETY_CRITERIA = [
        {"name": "cash_reserves", "question": "Does the company maintain >18 months of operating cash?", "weight": 0.20},
        {"name": "debt_structure", "question": "Is debt long-dated with no covenant triggers?", "weight": 0.15},
        {"name": "revenue_diversity", "question": "Is revenue diversified across >3 uncorrelated streams?", "weight": 0.15},
        {"name": "operational_redundancy", "question": "Are there backup suppliers, systems, and facilities?", "weight": 0.15},
        {"name": "regulatory_buffer", "question": "Does the company exceed regulatory minimums by >50%?", "weight": 0.10},
        {"name": "talent_retention", "question": "Is key-person risk mitigated?", "weight": 0.10},
        {"name": "insurance_coverage", "question": "Are catastrophic scenarios insured or hedged?", "weight": 0.10},
        {"name": "lindy_compliance", "question": "Has the core business model survived >10 years?", "weight": 0.05},
    ]

    UPSIDE_CRITERIA = [
        {"name": "asymmetric_payoff", "question": "Is the downside capped but the upside unbounded?", "weight": 0.25},
        {"name": "small_bet_size", "question": "Is total investment <10% of available capital?", "weight": 0.20},
        {"name": "optionality", "question": "Can the bet be abandoned at low cost if it doesn't work?", "weight": 0.20},
        {"name": "antifragile_trigger", "question": "Does the bet gain value from market chaos or volatility?", "weight": 0.15},
        {"name": "information_advantage", "question": "Is there a genuine information or structural edge?", "weight": 0.10},
        {"name": "scalability", "question": "If successful, can the position be scaled 10x?", "weight": 0.10},
    ]

    @classmethod
    def analyze(cls, proposal: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate a barbell strategy framework assessment for a proposal."""
        context = context or {}
        return {
            "framework": "barbell_strategy",
            "timestamp": datetime.utcnow().isoformat(),
            "proposal_summary": proposal[:500],
            "safety_side": {
                "allocation": "85-90% of capital/resources",
                "criteria": cls.SAFETY_CRITERIA,
                "principle": "Survive ALL scenarios. No single failure mode can cause ruin.",
                "key_questions": [c["question"] for c in cls.SAFETY_CRITERIA],
            },
            "upside_side": {
                "allocation": "10-15% of capital/resources",
                "criteria": cls.UPSIDE_CRITERIA,
                "principle": "Small bets with convex payoff. Failure = small loss. Success = transformation.",
                "key_questions": [c["question"] for c in cls.UPSIDE_CRITERIA],
            },
            "forbidden_middle": {
                "description": "The fragile zone: moderate risk for moderate return.",
                "red_flags": [
                    "Strategies promising 'balanced' risk-return with leverage",
                    "Optimized portfolios without tail-risk hedging",
                    "Single large bets representing 20-40% of capital",
                    "Dependence on a single revenue stream or customer",
                    "Operational efficiency that removes all slack and buffers",
                ],
            },
            "decision_matrix": cls._build_decision_prompt(proposal, context),
        }

    @classmethod
    def _build_decision_prompt(cls, proposal: str, context: Dict) -> str:
        return f"""BARBELL STRATEGY ASSESSMENT

PROPOSAL: {proposal[:300]}

STEP 1 — SAFETY AUDIT (Is the base indestructible?)
Rate each criterion 1-10:
{chr(10).join(f'  - {c["name"]}: {c["question"]}' for c in cls.SAFETY_CRITERIA)}

STEP 2 — UPSIDE AUDIT (Is the bet convex?)
Rate each criterion 1-10:
{chr(10).join(f'  - {c["name"]}: {c["question"]}' for c in cls.UPSIDE_CRITERIA)}

STEP 3 — MIDDLE DETECTION (Is anything stuck in the fragile middle?)
Identify any elements that carry moderate risk without asymmetric upside.

STEP 4 — BARBELL VERDICT
Classify the proposal: BARBELL-ALIGNED / NEEDS-RESTRUCTURING / FRAGILE"""


class BlackSwanScanner:
    """
    Systematic identification of Black Swan risks.

    Based on Taleb's framework:
    - Black Swans are RARE, HIGH-IMPACT, and RETROSPECTIVELY PREDICTABLE
    - Focus on second-order effects and cascading failures
    - Look for hidden correlations that emerge in crisis
    """

    RISK_CATEGORIES = [
        {
            "category": "concentration_risk",
            "name": "Concentration & Single Points of Failure",
            "signals": [
                "Revenue concentration >30% from single client/product",
                "Geographic concentration in politically unstable region",
                "Technology dependence on single vendor or platform",
                "Key-person dependence without succession plan",
                "Supply chain bottleneck through single corridor",
            ],
        },
        {
            "category": "leverage_and_liquidity",
            "name": "Leverage & Liquidity Traps",
            "signals": [
                "Debt/equity ratio >2x without matching cash flows",
                "Short-term debt financing long-term assets",
                "Margin calls or covenant triggers within 2 sigma move",
                "Counterparty risk concentrated in single institution",
                "Mark-to-market losses in illiquid positions",
            ],
        },
        {
            "category": "regime_change",
            "name": "Regime Change & Paradigm Shifts",
            "signals": [
                "Business model assumes stable regulatory environment",
                "Revenue depends on continuation of current monetary policy",
                "Technology disruption could obsolete core product in <3 years",
                "Demographic shifts undermining customer base",
                "Climate or geopolitical events affecting supply chain",
            ],
        },
        {
            "category": "hidden_correlation",
            "name": "Hidden Correlations (Crisis Coupling)",
            "signals": [
                "Assets that appear uncorrelated but share liquidity providers",
                "Diversification that disappears in market stress",
                "Revenue streams tied to same macro factor",
                "Insurance/hedging counterparty shares risk exposure",
                "Global supply chains with hidden geographic overlap",
            ],
        },
        {
            "category": "iatrogenic_risk",
            "name": "Iatrogenic Risk (Self-Inflicted Harm)",
            "signals": [
                "Over-optimization removing all operational slack",
                "Excessive complexity in organizational structure",
                "Process improvements that increase fragility",
                "Risk models that create false confidence",
                "Cost-cutting that eliminates redundancy buffers",
            ],
        },
        {
            "category": "cascade_failure",
            "name": "Cascade & Contagion Pathways",
            "signals": [
                "Failure in one unit triggers margin call in another",
                "Reputational damage causing customer/partner exodus",
                "Loss of key relationship triggering contractual defaults",
                "Cyber breach exposing interconnected systems",
                "Regulatory action in one jurisdiction affecting global operations",
            ],
        },
    ]

    @classmethod
    def scan(cls, proposal: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate a Black Swan risk scan for a proposal."""
        return {
            "framework": "black_swan_scan",
            "timestamp": datetime.utcnow().isoformat(),
            "proposal_summary": proposal[:500],
            "risk_categories": cls.RISK_CATEGORIES,
            "scan_protocol": cls._build_scan_prompt(proposal),
            "severity_scale": {
                "EXISTENTIAL": "Company-ending event. Probability low but non-zero.",
                "SEVERE": "50%+ capital destruction. Multi-year recovery.",
                "SIGNIFICANT": "Major setback, 20-50% value destruction.",
                "MODERATE": "Painful but survivable drawdown.",
            },
            "response_framework": {
                "detect": "Identify the tail risk scenario in concrete terms",
                "probability": "Estimate — but admit the limits of estimation",
                "impact": "Map the second-order and third-order effects",
                "hedge": "What is the cheapest insurance against this scenario?",
                "benefit": "Can we restructure to GAIN from this scenario?",
            },
        }

    @classmethod
    def _build_scan_prompt(cls, proposal: str) -> str:
        categories_text = ""
        for cat in cls.RISK_CATEGORIES:
            categories_text += f"\n### {cat['name']}\n"
            for signal in cat["signals"]:
                categories_text += f"  - [ ] {signal}\n"
        return f"""BLACK SWAN RISK SCAN

PROPOSAL: {proposal[:300]}

Scan each risk category and flag any that apply:
{categories_text}

For each flagged risk:
1. Describe the specific scenario
2. Estimate severity: EXISTENTIAL / SEVERE / SIGNIFICANT / MODERATE
3. Identify the cheapest hedge or structural fix
4. Determine if the risk can be converted to an antifragile opportunity"""


class AlphaExtractor:
    """
    Quantitative signal extraction framework inspired by Renaissance Technologies.

    Evaluates proposals for exploitable statistical edges, signal decay,
    capacity constraints, and systematic implementation potential.
    """

    SIGNAL_TYPES = [
        {
            "type": "structural",
            "name": "Structural Edge",
            "description": "Persistent advantage from market microstructure, regulation, or access",
            "decay_rate": "slow (years)",
            "examples": ["Regulatory barriers", "Network effects", "Proprietary data", "Speed advantage"],
        },
        {
            "type": "behavioral",
            "name": "Behavioral Edge",
            "description": "Exploiting systematic human biases and institutional constraints",
            "decay_rate": "medium (months to years)",
            "examples": ["Overreaction to news", "Anchoring bias", "Loss aversion", "Herding"],
        },
        {
            "type": "informational",
            "name": "Informational Edge",
            "description": "Access to or superior processing of public/private information",
            "decay_rate": "fast (days to weeks)",
            "examples": ["Alternative data", "Faster processing", "Novel data combination", "NLP on filings"],
        },
        {
            "type": "analytical",
            "name": "Analytical Edge",
            "description": "Superior models or frameworks for interpreting available data",
            "decay_rate": "medium (months)",
            "examples": ["Better risk models", "Regime detection", "Non-linear relationships", "Cross-asset signals"],
        },
    ]

    @classmethod
    def extract(cls, proposal: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Evaluate a proposal through quantitative alpha extraction lens."""
        return {
            "framework": "alpha_extraction",
            "timestamp": datetime.utcnow().isoformat(),
            "proposal_summary": proposal[:500],
            "signal_types": cls.SIGNAL_TYPES,
            "evaluation_protocol": cls._build_extraction_prompt(proposal),
            "quality_metrics": {
                "sharpe_threshold": "Signal should survive >1.5 Sharpe after costs",
                "statistical_significance": "t-stat > 2.0 out-of-sample required",
                "independence": "Must not be repackaged factor exposure",
                "capacity": "Must support meaningful capital deployment",
                "robustness": "Must work across 3+ market regimes",
            },
        }

    @classmethod
    def _build_extraction_prompt(cls, proposal: str) -> str:
        return f"""ALPHA EXTRACTION ASSESSMENT

PROPOSAL: {proposal[:300]}

SIGNAL IDENTIFICATION:
For each potential signal:
1. What is the exploitable pattern or edge?
2. What EVIDENCE supports its existence? (Data, not narrative)
3. What is the DECAY RATE? (How quickly is it arbitraged away?)
4. What is the CAPACITY? (How much capital before market impact kills it?)
5. What are the TRANSACTION COSTS? (Does the signal survive after friction?)

FACTOR DECOMPOSITION (Asness test):
- Run a mental Fama-French regression. Is this alpha or repackaged beta?
- Factors to check: Market, Value (HML), Size (SMB), Momentum (UMD),
  Quality (QMJ), Low-Vol (BAB), Carry

MODEL RISK ASSESSMENT:
- What assumptions does the model make?
- What would BREAK the model?
- How do you know when to TURN IT OFF?

VERDICT: SIGNAL / NOISE / AMBIGUOUS"""


class ConvexityMapper:
    """
    Maps the payoff profile of a strategy or decision.

    Convex = gains more from upside than it loses from downside (antifragile)
    Concave = loses more from downside than it gains from upside (fragile)
    Linear = symmetric gains and losses (robust but not antifragile)
    """

    @classmethod
    def map_payoff(cls, proposal: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate convexity/concavity assessment of a proposal."""
        return {
            "framework": "convexity_mapping",
            "timestamp": datetime.utcnow().isoformat(),
            "proposal_summary": proposal[:500],
            "payoff_profiles": {
                "convex": {
                    "description": "Limited downside, expanding upside. Gains from volatility.",
                    "characteristics": [
                        "Option-like payoff (premium = max loss)",
                        "Benefits from uncertainty and volatility",
                        "Small experiments with big potential payoffs",
                        "Right to participate, no obligation to continue",
                    ],
                    "examples": [
                        "R&D investment (cost = budget, upside = breakthrough)",
                        "Venture portfolio (lose 1x, gain 100x)",
                        "Out-of-the-money puts (small premium, crash protection)",
                    ],
                },
                "concave": {
                    "description": "Limited upside, expanding downside. Harmed by volatility.",
                    "characteristics": [
                        "Sells insurance (collects premium, exposed to catastrophe)",
                        "Leveraged carry trades",
                        "Short volatility positions",
                        "Optimization without redundancy",
                    ],
                    "examples": [
                        "Writing naked options",
                        "High-leverage debt structures",
                        "Just-in-time with no buffers",
                    ],
                },
                "linear": {
                    "description": "Proportional gains and losses. Neutral to volatility.",
                    "characteristics": [
                        "Direct ownership without leverage",
                        "Simple buy-and-hold equity",
                        "Commodity exposure without derivatives",
                    ],
                },
            },
            "assessment_prompt": cls._build_mapping_prompt(proposal),
        }

    @classmethod
    def _build_mapping_prompt(cls, proposal: str) -> str:
        return f"""CONVEXITY MAP

PROPOSAL: {proposal[:300]}

For each major component of this proposal, classify:

| Component | Payoff Shape | Downside Cap | Upside Potential | Net Convexity |
|-----------|-------------|-------------|-----------------|---------------|
| [...]     | Convex/Concave/Linear | $ or % | $ or % | Score -5 to +5 |

OVERALL ASSESSMENT:
- NET PORTFOLIO CONVEXITY: [Score from -5 (dangerously concave) to +5 (beautifully convex)]
- VOLATILITY SENSITIVITY: Does total value increase or decrease with more uncertainty?
- RESTRUCTURING ADVICE: How to shift concave elements toward convexity

TALEB TEST: "Does this strategy benefit from the unexpected?"
SPITZNAGEL TEST: "What is the portfolio-level crash payoff?"
SIMONS TEST: "Is the edge statistically real or narrative-driven?"
ASNESS TEST: "Is this alpha or disguised factor exposure?" """
