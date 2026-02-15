"""
Bitmask barrier synchronization and confidence-weighted hybrid voting.

Uses Python IntFlag to track agent completions as a bitmask. Each agent
corresponds to a bit position. An evaluation can only transition to
"action needed" when completed_agents == ALL_REQUIRED.

Voting combines two tracks:
  1. TA agents produce numerical scores (0-100) weighted by confidence.
  2. LLM agents produce directional opinions resolved by majority vote.
  The two tracks combine with configurable weights for a final conviction score.
"""

from __future__ import annotations

import logging
import time
from enum import IntFlag, auto
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from shared.state_schema import (
    ConvictionScore,
    Direction,
    EvaluationStatus,
    LLMOpinion,
    TAScore,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Bitmask agent flags
# ---------------------------------------------------------------------------

class AgentFlags(IntFlag):
    """
    Bitmask flags for tracking agent completion.

    Each agent is a single bit. ALL_REQUIRED is the bitwise OR of
    every agent that must complete before state transition.

    Extensible: adding a new agent means adding one flag and
    OR-ing it into ALL_REQUIRED.
    """
    NONE = 0

    # Technical Analysis agents
    TA_RSI = auto()
    TA_MACD = auto()
    TA_VOLUME = auto()
    TA_BOLLINGER = auto()

    # LLM Council agents
    LLM_SENTIMENT = auto()
    LLM_FUNDAMENTAL = auto()
    LLM_MACRO = auto()

    # Combined required sets
    ALL_TA = TA_RSI | TA_MACD | TA_VOLUME | TA_BOLLINGER
    ALL_LLM = LLM_SENTIMENT | LLM_FUNDAMENTAL | LLM_MACRO
    ALL_REQUIRED = ALL_TA | ALL_LLM

    # Minimum viable sets for degraded mode
    MIN_TA = TA_RSI | TA_MACD
    MIN_LLM = LLM_SENTIMENT


# Map from agent name strings to flags for dynamic resolution
AGENT_FLAG_MAP: Dict[str, AgentFlags] = {
    "ta_rsi": AgentFlags.TA_RSI,
    "ta_macd": AgentFlags.TA_MACD,
    "ta_volume": AgentFlags.TA_VOLUME,
    "ta_bollinger": AgentFlags.TA_BOLLINGER,
    "llm_sentiment": AgentFlags.LLM_SENTIMENT,
    "llm_fundamental": AgentFlags.LLM_FUNDAMENTAL,
    "llm_macro": AgentFlags.LLM_MACRO,
}


# ---------------------------------------------------------------------------
# Bitmask barrier
# ---------------------------------------------------------------------------

@dataclass
class BarrierStatus:
    completed: AgentFlags = AgentFlags.NONE
    missing: AgentFlags = AgentFlags.NONE
    is_complete: bool = False
    is_viable: bool = False
    completion_pct: float = 0.0


class BitmaskBarrier:
    """
    Barrier synchronization using bitmask completion tracking.

    O(1) completion checking. Missing-agent diagnostic is immediate:
    ALL_REQUIRED & ~completed reveals exactly which agents haven't reported.
    """

    def __init__(
        self,
        required: AgentFlags = AgentFlags.ALL_REQUIRED,
        minimum_viable: Optional[AgentFlags] = None,
        timeout_seconds: float = 120.0,
    ):
        self.required = required
        self.minimum_viable = minimum_viable or (AgentFlags.MIN_TA | AgentFlags.MIN_LLM)
        self.timeout_seconds = timeout_seconds
        self._completed = AgentFlags.NONE
        self._start_time: Optional[float] = None
        self._agent_times: Dict[str, float] = {}

    def start(self) -> None:
        self._start_time = time.monotonic()
        self._completed = AgentFlags.NONE
        self._agent_times.clear()

    def mark_complete(self, agent_name: str) -> BarrierStatus:
        """Mark an agent as complete and return current barrier status."""
        flag = AGENT_FLAG_MAP.get(agent_name)
        if flag is None:
            logger.warning(f"Unknown agent name for barrier: {agent_name}")
            return self.status()

        self._completed |= flag
        self._agent_times[agent_name] = time.monotonic()
        logger.info(
            f"Barrier: {agent_name} complete. "
            f"Progress: {bin(self._completed)} / {bin(self.required)}"
        )
        return self.status()

    def mark_failed(self, agent_name: str) -> None:
        """Record that an agent failed (does NOT set its completion bit)."""
        logger.warning(f"Barrier: {agent_name} FAILED, not marking complete")

    def status(self) -> BarrierStatus:
        missing = self.required & ~self._completed
        total_bits = bin(self.required).count("1")
        done_bits = bin(self._completed & self.required).count("1")
        return BarrierStatus(
            completed=self._completed,
            missing=missing,
            is_complete=(self._completed & self.required) == self.required,
            is_viable=(self._completed & self.minimum_viable) == self.minimum_viable,
            completion_pct=done_bits / total_bits if total_bits > 0 else 0.0,
        )

    def is_timed_out(self) -> bool:
        if self._start_time is None:
            return False
        return (time.monotonic() - self._start_time) > self.timeout_seconds

    def get_missing_agents(self) -> List[str]:
        missing = self.required & ~self._completed
        return [name for name, flag in AGENT_FLAG_MAP.items() if missing & flag]

    def get_completed_agents(self) -> List[str]:
        return [name for name, flag in AGENT_FLAG_MAP.items() if self._completed & flag]


# ---------------------------------------------------------------------------
# Confidence-weighted hybrid voting aggregator
# ---------------------------------------------------------------------------

class HybridVotingAggregator:
    """
    Two-track voting mechanism:
      Track 1 (TA): Numerical scores (0-100) weighted by confidence.
      Track 2 (LLM): Directional opinions resolved by majority vote.

    Tracks combine with configurable weights (default 60/40) for a
    final conviction score in [-1.0, +1.0].
    """

    def __init__(self, ta_weight: float = 0.6, llm_weight: float = 0.4):
        if not abs(ta_weight + llm_weight - 1.0) < 0.001:
            raise ValueError(f"Weights must sum to 1.0, got {ta_weight + llm_weight}")
        self.ta_weight = ta_weight
        self.llm_weight = llm_weight
        self._ta_scores: List[TAScore] = []
        self._llm_opinions: List[LLMOpinion] = []

    def add_ta_score(self, score: TAScore) -> None:
        self._ta_scores.append(score)

    def add_llm_opinion(self, opinion: LLMOpinion) -> None:
        self._llm_opinions.append(opinion)

    def compute_ta_weighted_score(self) -> float:
        """
        Confidence-weighted average of TA scores.
        Returns a value in [0, 100].
        """
        if not self._ta_scores:
            return 50.0  # neutral
        total_weight = sum(s.confidence for s in self._ta_scores)
        if total_weight == 0:
            return 50.0
        weighted_sum = sum(s.score * s.confidence for s in self._ta_scores)
        return weighted_sum / total_weight

    def compute_llm_consensus(self) -> Tuple[Direction, float]:
        """
        Majority vote over LLM opinions.
        Returns (majority direction, agreement ratio).
        """
        if not self._llm_opinions:
            return Direction.NEUTRAL, 0.0

        vote_counts: Dict[Direction, float] = {
            Direction.BULLISH: 0.0,
            Direction.BEARISH: 0.0,
            Direction.NEUTRAL: 0.0,
        }
        for opinion in self._llm_opinions:
            vote_counts[opinion.direction] += opinion.confidence

        total = sum(vote_counts.values())
        if total == 0:
            return Direction.NEUTRAL, 0.0

        winner = max(vote_counts, key=vote_counts.get)  # type: ignore
        agreement = vote_counts[winner] / total
        return winner, agreement

    def _direction_to_score(self, direction: Direction, agreement: float) -> float:
        """Convert LLM direction to a [-1.0, +1.0] score."""
        multiplier = {
            Direction.BULLISH: 1.0,
            Direction.BEARISH: -1.0,
            Direction.NEUTRAL: 0.0,
        }
        return multiplier[direction] * agreement

    def aggregate(self, ticker: str = "") -> ConvictionScore:
        """
        Combine TA and LLM tracks into a final conviction score.

        TA score (0-100) is normalized to [-1, 1]: (score - 50) / 50.
        LLM consensus direction * agreement gives [-1, 1].
        Combined = ta_weight * ta_normalized + llm_weight * llm_score.
        """
        ta_score = self.compute_ta_weighted_score()
        ta_normalized = (ta_score - 50.0) / 50.0  # map 0-100 -> -1 to +1

        llm_direction, llm_agreement = self.compute_llm_consensus()
        llm_score = self._direction_to_score(llm_direction, llm_agreement)

        combined = self.ta_weight * ta_normalized + self.llm_weight * llm_score
        combined = max(-1.0, min(1.0, combined))

        return ConvictionScore(
            ticker=ticker,
            ta_weighted_score=ta_score,
            llm_consensus=llm_direction,
            llm_agreement_ratio=llm_agreement,
            combined_score=combined,
            ta_weight=self.ta_weight,
            llm_weight=self.llm_weight,
            participating_agents=(
                [s.agent_name for s in self._ta_scores]
                + [o.agent_name for o in self._llm_opinions]
            ),
        )

    def reset(self) -> None:
        self._ta_scores.clear()
        self._llm_opinions.clear()
