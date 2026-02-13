"""Tests for the scoring system."""

import pytest

from src.models.plant_state import PlantState
from src.models.constants import STEADY_STATE, LIMITS
from src.safety.safety_system import SafetyResult
from src.scoring.tracker import ScoreTracker, TurnScore


def _make_state(**overrides) -> PlantState:
    d = {**STEADY_STATE, **overrides}
    return PlantState.from_dict(d)


class TestTurnScoring:
    def test_perfect_state_high_score(self):
        """Near-perfect state should score high."""
        scorer = ScoreTracker()
        state = _make_state(xB_sd=0.9990, dP_col=0.01, L_Drum=0.50, L_Bot=0.50)
        safety = SafetyResult()
        score = scorer.score_turn(1, state, safety)
        assert score.total >= 70

    def test_off_spec_reduces_purity_score(self):
        scorer = ScoreTracker()
        state_good = _make_state(xB_sd=0.9990)
        state_bad = _make_state(xB_sd=0.990)
        safety = SafetyResult()
        s1 = scorer.score_turn(1, state_good, safety)
        s2 = scorer.score_turn(2, state_bad, safety)
        assert s1.purity_score > s2.purity_score

    def test_high_dP_reduces_pressure_score(self):
        scorer = ScoreTracker()
        state_good = _make_state(dP_col=0.05)
        state_bad = _make_state(dP_col=0.28)
        safety = SafetyResult()
        s1 = scorer.score_turn(1, state_good, safety)
        s2 = scorer.score_turn(2, state_bad, safety)
        assert s1.pressure_score > s2.pressure_score

    def test_esd_penalty(self):
        scorer = ScoreTracker()
        state = _make_state()
        safety = SafetyResult(esd_triggered=True, esd_reason="test")
        score = scorer.score_turn(1, state, safety)
        assert score.safety_penalty == -20.0
        assert scorer.esd_count == 1

    def test_interlock_penalty(self):
        scorer = ScoreTracker()
        state = _make_state()
        safety = SafetyResult(interlock_active=True, interlock_reason="test")
        score = scorer.score_turn(1, state, safety)
        assert score.safety_penalty == -10.0
        assert scorer.interlock_count == 1

    def test_alarm_penalty(self):
        scorer = ScoreTracker()
        state = _make_state()
        safety = SafetyResult(alarms=["alarm1", "alarm2"])
        score = scorer.score_turn(1, state, safety)
        assert score.safety_penalty == -6.0
        assert scorer.alarm_count == 2

    def test_score_never_negative(self):
        scorer = ScoreTracker()
        state = _make_state(xB_sd=0.80, dP_col=0.35)
        safety = SafetyResult(esd_triggered=True, esd_reason="test")
        score = scorer.score_turn(1, state, safety)
        assert score.total >= 0.0


class TestScoreTracker:
    def test_average_empty(self):
        scorer = ScoreTracker()
        assert scorer.average_score == 0.0

    def test_average_after_turns(self):
        scorer = ScoreTracker()
        state = _make_state()
        safety = SafetyResult()
        scorer.score_turn(1, state, safety)
        scorer.score_turn(2, state, safety)
        assert scorer.average_score > 0.0

    def test_summary(self):
        scorer = ScoreTracker()
        state = _make_state()
        safety = SafetyResult()
        scorer.score_turn(1, state, safety)
        s = scorer.summary()
        assert s["turns"] == 1
        assert "grade" in s
        assert "esd_trips" in s

    def test_grade_mapping(self):
        scorer = ScoreTracker()
        # Near-perfect state -> high grade
        state = _make_state(xB_sd=0.9990, dP_col=0.01, L_Drum=0.50, L_Bot=0.50)
        safety = SafetyResult()
        scorer.score_turn(1, state, safety)
        assert scorer.overall_grade in ("A", "B")


class TestTurnScoreGrade:
    def test_grade_a(self):
        score = TurnScore(turn=1, purity_score=38, pressure_score=19, level_score=18, safety_penalty=0, total=95)
        assert score.grade == "A"

    def test_grade_f(self):
        score = TurnScore(turn=1, purity_score=10, pressure_score=5, level_score=5, safety_penalty=-20, total=10)
        assert score.grade == "F"
