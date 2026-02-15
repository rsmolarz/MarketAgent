"""
AI Advisory Board - Multi-Agent Debate System

A simulation of an investment committee featuring AI personas modeled after
Nassim Nicholas Taleb, Mark Spitznagel, Jim Simons, and Cliff Asness.
Each advisor brings distinct epistemological frameworks to evaluate corporate
strategy decisions through the lens of antifragility, tail-risk hedging,
quantitative signal extraction, and factor-based systematic investing.
"""

from advisory_board.personas import ADVISORS, get_advisor
from advisory_board.engine import AdvisoryBoardEngine
from advisory_board.frameworks import (
    BarbellAnalyzer,
    BlackSwanScanner,
    AlphaExtractor,
    ConvexityMapper,
)

__all__ = [
    "ADVISORS",
    "get_advisor",
    "AdvisoryBoardEngine",
    "BarbellAnalyzer",
    "BlackSwanScanner",
    "AlphaExtractor",
    "ConvexityMapper",
]
