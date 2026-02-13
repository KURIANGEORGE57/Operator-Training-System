"""Operator performance scoring system.

Tracks how well the operator maintains the plant within specifications.
Penalties for off-spec product, safety events, and ESD trips.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Dict

from src.models.constants import LIMITS
from src.models.plant_state import PlantState
from src.safety.safety_system import SafetyResult


@dataclass
class TurnScore:
    """Score breakdown for a single turn."""

    turn: int
    purity_score: float     # 0-40 points
    pressure_score: float   # 0-20 points
    level_score: float      # 0-20 points
    safety_penalty: float   # 0 to -20 points
    total: float

    @property
    def grade(self) -> str:
        if self.total >= 90:
            return "A"
        if self.total >= 80:
            return "B"
        if self.total >= 70:
            return "C"
        if self.total >= 60:
            return "D"
        return "F"


class ScoreTracker:
    """Accumulates operator performance across turns."""

    def __init__(self):
        self.history: List[TurnScore] = []
        self.esd_count: int = 0
        self.interlock_count: int = 0
        self.alarm_count: int = 0

    def score_turn(
        self, turn: int, state: PlantState, safety: SafetyResult
    ) -> TurnScore:
        """Evaluate operator performance for one turn."""

        # Purity: 40 points max, Gaussian penalty on deviation from spec
        xB_err = abs(state.xB_sd - LIMITS.xB_spec)
        purity = 40.0 * math.exp(-((xB_err / 0.005) ** 2))

        # Pressure: 20 points max, penalty as dP approaches alarm threshold
        dP_frac = state.dP_col / LIMITS.dP_alarm
        pressure = 20.0 * max(0.0, 1.0 - dP_frac ** 2)

        # Levels: 20 points max, penalty for deviation from 0.5 midpoint
        drum_err = abs(state.L_Drum - 0.5)
        bot_err = abs(state.L_Bot - 0.5)
        level = 20.0 * math.exp(-((drum_err / 0.3) ** 2 + (bot_err / 0.3) ** 2))

        # Safety penalties
        penalty = 0.0
        if safety.esd_triggered:
            penalty = -20.0
            self.esd_count += 1
        elif safety.interlock_active:
            penalty = -10.0
            self.interlock_count += 1
        elif safety.alarms:
            penalty = -3.0 * len(safety.alarms)
            self.alarm_count += len(safety.alarms)

        total = max(0.0, purity + pressure + level + penalty)

        score = TurnScore(
            turn=turn,
            purity_score=round(purity, 1),
            pressure_score=round(pressure, 1),
            level_score=round(level, 1),
            safety_penalty=round(penalty, 1),
            total=round(total, 1),
        )
        self.history.append(score)
        return score

    @property
    def average_score(self) -> float:
        if not self.history:
            return 0.0
        return round(sum(s.total for s in self.history) / len(self.history), 1)

    @property
    def overall_grade(self) -> str:
        avg = self.average_score
        if avg >= 90:
            return "A"
        if avg >= 80:
            return "B"
        if avg >= 70:
            return "C"
        if avg >= 60:
            return "D"
        return "F"

    def summary(self) -> Dict[str, object]:
        return {
            "turns": len(self.history),
            "average_score": self.average_score,
            "grade": self.overall_grade,
            "esd_trips": self.esd_count,
            "interlocks": self.interlock_count,
            "alarms": self.alarm_count,
        }
