"""Tests for the three-tier safety system."""

import pytest

from src.models.plant_state import PlantState
from src.models.constants import LIMITS, STEADY_STATE
from src.safety.safety_system import evaluate_safety, SafetyResult


def _make_state(**overrides) -> PlantState:
    """Create a PlantState with optional overrides from steady state."""
    d = {**STEADY_STATE, **overrides}
    return PlantState.from_dict(d)


def _default_u():
    return {"SP_F_Reflux": 25.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}


# ---------------------------------------------------------------------------
# Tier 1: Alarms
# ---------------------------------------------------------------------------


class TestAlarms:
    def test_high_dP_alarm(self):
        state = _make_state(dP_col=0.31)
        result = evaluate_safety(state, _default_u())
        assert any("HIGH dP" in a for a in result.alarms)

    def test_high_T_alarm(self):
        state = _make_state(T_top=101.0)
        result = evaluate_safety(state, _default_u())
        assert any("HIGH T_top" in a for a in result.alarms)

    def test_off_spec_alarm(self):
        state = _make_state(xB_sd=0.9985)
        result = evaluate_safety(state, _default_u())
        assert any("OFF-SPEC" in a for a in result.alarms)

    def test_low_drum_alarm(self):
        state = _make_state(L_Drum=0.08)
        result = evaluate_safety(state, _default_u())
        assert any("LOW drum" in a for a in result.alarms)

    def test_low_bottoms_alarm(self):
        state = _make_state(L_Bot=0.08)
        result = evaluate_safety(state, _default_u())
        assert any("LOW bottoms" in a for a in result.alarms)

    def test_multiple_alarms(self):
        state = _make_state(dP_col=0.31, T_top=101.0, xB_sd=0.998)
        result = evaluate_safety(state, _default_u())
        assert len(result.alarms) >= 3

    def test_no_alarm_in_normal(self):
        state = _make_state(xB_sd=0.9995)
        result = evaluate_safety(state, _default_u())
        assert len(result.alarms) == 0
        assert result.is_clear


# ---------------------------------------------------------------------------
# Tier 2: Interlocks
# ---------------------------------------------------------------------------


class TestInterlocks:
    def test_flooding_interlock_triggered(self):
        state = _make_state(dP_col=0.335)
        result = evaluate_safety(state, _default_u())
        assert result.interlock_active
        assert "Flooding" in result.interlock_reason

    def test_interlock_reduces_reboil(self):
        u = {"SP_F_Reflux": 25.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}
        state = _make_state(dP_col=0.335)
        result = evaluate_safety(state, u)
        assert result.adjusted_inputs["SP_F_Reboil"] < u["SP_F_Reboil"]

    def test_interlock_reboil_floor(self):
        u = {"SP_F_Reflux": 25.0, "SP_F_Reboil": 0.35, "SP_F_ToTol": 55.0}
        state = _make_state(dP_col=0.335)
        result = evaluate_safety(state, u)
        assert result.adjusted_inputs["SP_F_Reboil"] >= 0.3

    def test_interlock_increases_reflux(self):
        u = {"SP_F_Reflux": 25.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}
        state = _make_state(dP_col=0.335)
        result = evaluate_safety(state, u)
        assert result.adjusted_inputs["SP_F_Reflux"] > u["SP_F_Reflux"]

    def test_interlock_reflux_ceiling(self):
        u = {"SP_F_Reflux": 44.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}
        state = _make_state(dP_col=0.335)
        result = evaluate_safety(state, u)
        assert result.adjusted_inputs["SP_F_Reflux"] <= 45.0

    def test_no_interlock_below_threshold(self):
        state = _make_state(dP_col=0.32)
        result = evaluate_safety(state, _default_u())
        assert not result.interlock_active


# ---------------------------------------------------------------------------
# Tier 3: Emergency Shutdown
# ---------------------------------------------------------------------------


class TestESD:
    def test_critical_dP_triggers_esd(self):
        state = _make_state(dP_col=0.35)
        result = evaluate_safety(state, _default_u())
        assert result.esd_triggered
        assert "dP" in result.esd_reason

    def test_critical_T_triggers_esd(self):
        state = _make_state(T_top=104.0)
        result = evaluate_safety(state, _default_u())
        assert result.esd_triggered
        assert "T" in result.esd_reason

    def test_critical_drum_level_triggers_esd(self):
        state = _make_state(L_Drum=0.04)
        result = evaluate_safety(state, _default_u())
        assert result.esd_triggered
        assert "drum" in result.esd_reason

    def test_exact_esd_threshold_no_trip(self):
        """At exactly the threshold, no ESD (must exceed)."""
        state = _make_state(dP_col=LIMITS.dP_esd)
        result = evaluate_safety(state, _default_u())
        assert not result.esd_triggered

    def test_just_above_esd_threshold(self):
        state = _make_state(dP_col=LIMITS.dP_esd + 0.001)
        result = evaluate_safety(state, _default_u())
        assert result.esd_triggered

    def test_esd_preempts_interlock(self):
        """ESD should trigger before interlock logic runs."""
        state = _make_state(dP_col=0.35)
        result = evaluate_safety(state, _default_u())
        assert result.esd_triggered
        # When ESD fires, we return early - no interlock
        assert not result.interlock_active

    def test_no_esd_in_normal(self):
        state = _make_state()
        result = evaluate_safety(state, _default_u())
        assert not result.esd_triggered


# ---------------------------------------------------------------------------
# Tier Integration
# ---------------------------------------------------------------------------


class TestSafetyIntegration:
    def test_alarm_and_interlock_together(self):
        """Interlock range also triggers alarm."""
        state = _make_state(dP_col=0.335)
        result = evaluate_safety(state, _default_u())
        assert result.interlock_active
        assert any("HIGH dP" in a for a in result.alarms)

    def test_esd_returns_early_no_alarms(self):
        """ESD returns immediately - no alarms populated."""
        state = _make_state(dP_col=0.35)
        result = evaluate_safety(state, _default_u())
        assert result.esd_triggered
        assert len(result.alarms) == 0

    def test_safety_clear_flag(self):
        state = _make_state(xB_sd=0.9995)
        result = evaluate_safety(state, _default_u())
        assert result.is_clear

    def test_alarm_clears_is_clear(self):
        state = _make_state(dP_col=0.31)
        result = evaluate_safety(state, _default_u())
        assert not result.is_clear
