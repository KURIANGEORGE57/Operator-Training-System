"""Unit tests for safety logic in the BTX Operator Training System.

This test suite verifies the critical safety systems:
1. Alarms - Early warnings for abnormal conditions
2. Interlocks - Automatic protective actions
3. Emergency Shutdown (ESD) - Last-resort safety measure
4. Move rate limiting - Prevents dangerous control changes

These tests are critical for ensuring the safety-critical system
operates correctly under all conditions.
"""

import pytest
import numpy as np
from typing import Dict


# Constants from app.py
LIMITS = {
    "dP_alarm": 0.30,
    "dP_trip": 0.33,
    "dP_esd": 0.34,
    "T_top_alarm": 100.0,
    "T_top_esd": 103.0,
    "xB_spec": 0.9990,
    "L_drum_min": 0.10,
    "L_drum_crit": 0.05,
}


def cap_moves(u_req: Dict, x_curr: Dict) -> Dict:
    """Rate limiter to prevent dangerous control changes.

    Implements per-turn move caps:
    - Reflux: ±2.0 t/h per turn
    - Reboiler: ±0.15 MW per turn
    - Toluene transfer: ±5.0 t/h per turn
    """
    caps = {"SP_F_Reflux": 2.0, "SP_F_Reboil": 0.15, "SP_F_ToTol": 5.0}
    u = u_req.copy()
    u["SP_F_Reflux"] = float(
        np.clip(
            u["SP_F_Reflux"],
            x_curr["F_Reflux"] - caps["SP_F_Reflux"],
            x_curr["F_Reflux"] + caps["SP_F_Reflux"],
        )
    )
    u["SP_F_Reboil"] = float(
        np.clip(
            u["SP_F_Reboil"],
            x_curr["F_Reboil"] - caps["SP_F_Reboil"],
            x_curr["F_Reboil"] + caps["SP_F_Reboil"],
        )
    )
    u["SP_F_ToTol"] = float(
        np.clip(
            u["SP_F_ToTol"],
            x_curr["F_ToTol"] - caps["SP_F_ToTol"],
            x_curr["F_ToTol"] + caps["SP_F_ToTol"],
        )
    )
    return u


def safety_logic(x_next: Dict, u_applied: Dict) -> Dict:
    """Three-tier safety system: alarms, interlocks, ESD.

    Returns:
        dict with keys:
            - alarms: list of alarm messages
            - interlock: list of interlock messages
            - adjust: dict of adjusted setpoints (if interlock active)
            - esd: bool indicating emergency shutdown
    """
    alarms, interlock, esd = [], [], False
    adjust = {}

    # Tier 1: Alarms (early warnings)
    if x_next["dP_col"] > LIMITS["dP_alarm"]:
        alarms.append("High column ΔP")
    if x_next["T_top"] > LIMITS["T_top_alarm"]:
        alarms.append("High overhead T")
    if x_next["xB_sd"] < LIMITS["xB_spec"]:
        alarms.append("Off-spec benzene purity")
    if x_next.get("L_Drum", 0.5) < LIMITS["L_drum_min"]:
        alarms.append("Low reflux drum level")

    # Tier 2: Interlock (automatic protective action)
    if x_next["dP_col"] > LIMITS["dP_trip"]:
        interlock.append("Flooding ILK: clamp reboil, increase reflux")
        adjust["SP_F_Reboil"] = max(u_applied["SP_F_Reboil"] - 0.2, 0.3)
        adjust["SP_F_Reflux"] = min(u_applied["SP_F_Reflux"] + 2.0, 45.0)

    # Tier 3: ESD (emergency shutdown)
    if (
        (x_next["dP_col"] > LIMITS["dP_esd"])
        or (x_next["T_top"] > LIMITS["T_top_esd"])
        or (x_next.get("L_Drum", 0.5) < LIMITS["L_drum_crit"])
    ):
        esd = True

    return {"alarms": alarms, "interlock": interlock, "adjust": adjust, "esd": esd}


# ===================================================================
# Test Suite
# ===================================================================


class TestAlarms:
    """Test alarm generation for early warning conditions."""

    def test_high_column_dp_alarm(self):
        """High column ΔP should trigger alarm."""
        x_next = {
            "dP_col": 0.31,  # Above alarm threshold (0.30)
            "T_top": 85.0,
            "xB_sd": 0.9995,
            "L_Drum": 0.5,
        }
        u_applied = {"SP_F_Reflux": 25.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}

        result = safety_logic(x_next, u_applied)

        assert "High column ΔP" in result["alarms"]
        assert not result["esd"]

    def test_high_overhead_temp_alarm(self):
        """High overhead temperature should trigger alarm."""
        x_next = {
            "dP_col": 0.15,
            "T_top": 101.0,  # Above alarm threshold (100.0)
            "xB_sd": 0.9995,
            "L_Drum": 0.5,
        }
        u_applied = {"SP_F_Reflux": 25.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}

        result = safety_logic(x_next, u_applied)

        assert "High overhead T" in result["alarms"]
        assert not result["esd"]

    def test_off_spec_benzene_purity_alarm(self):
        """Off-spec benzene purity should trigger alarm."""
        x_next = {
            "dP_col": 0.15,
            "T_top": 85.0,
            "xB_sd": 0.9985,  # Below spec threshold (0.9990)
            "L_Drum": 0.5,
        }
        u_applied = {"SP_F_Reflux": 25.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}

        result = safety_logic(x_next, u_applied)

        assert "Off-spec benzene purity" in result["alarms"]
        assert not result["esd"]

    def test_low_drum_level_alarm(self):
        """Low reflux drum level should trigger alarm."""
        x_next = {
            "dP_col": 0.15,
            "T_top": 85.0,
            "xB_sd": 0.9995,
            "L_Drum": 0.08,  # Below alarm threshold (0.10)
        }
        u_applied = {"SP_F_Reflux": 25.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}

        result = safety_logic(x_next, u_applied)

        assert "Low reflux drum level" in result["alarms"]
        assert not result["esd"]

    def test_multiple_alarms(self):
        """Multiple simultaneous alarms should all be reported."""
        x_next = {
            "dP_col": 0.31,  # High ΔP alarm
            "T_top": 101.0,  # High T alarm
            "xB_sd": 0.9985,  # Off-spec alarm
            "L_Drum": 0.08,  # Low level alarm
        }
        u_applied = {"SP_F_Reflux": 25.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}

        result = safety_logic(x_next, u_applied)

        assert len(result["alarms"]) == 4
        assert "High column ΔP" in result["alarms"]
        assert "High overhead T" in result["alarms"]
        assert "Off-spec benzene purity" in result["alarms"]
        assert "Low reflux drum level" in result["alarms"]

    def test_no_alarms_normal_operation(self):
        """Normal operating conditions should not trigger alarms."""
        x_next = {
            "dP_col": 0.15,
            "T_top": 85.0,
            "xB_sd": 0.9995,
            "L_Drum": 0.5,
        }
        u_applied = {"SP_F_Reflux": 25.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}

        result = safety_logic(x_next, u_applied)

        assert len(result["alarms"]) == 0
        assert not result["esd"]


class TestInterlocks:
    """Test automatic protective interlocks."""

    def test_flooding_interlock_triggers(self):
        """Flooding interlock should trigger when ΔP exceeds trip threshold."""
        x_next = {
            "dP_col": 0.335,  # Above trip threshold (0.33)
            "T_top": 85.0,
            "xB_sd": 0.9995,
            "L_Drum": 0.5,
        }
        u_applied = {"SP_F_Reflux": 25.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}

        result = safety_logic(x_next, u_applied)

        assert len(result["interlock"]) == 1
        assert "Flooding ILK" in result["interlock"][0]
        assert "SP_F_Reboil" in result["adjust"]
        assert "SP_F_Reflux" in result["adjust"]

    def test_flooding_interlock_reduces_reboiler(self):
        """Flooding interlock should reduce reboiler duty by 0.2 MW."""
        x_next = {
            "dP_col": 0.335,
            "T_top": 85.0,
            "xB_sd": 0.9995,
            "L_Drum": 0.5,
        }
        u_applied = {"SP_F_Reflux": 25.0, "SP_F_Reboil": 1.5, "SP_F_ToTol": 55.0}

        result = safety_logic(x_next, u_applied)

        # Should reduce reboiler by 0.2 MW
        expected_reboil = 1.5 - 0.2  # = 1.3
        assert result["adjust"]["SP_F_Reboil"] == expected_reboil

    def test_flooding_interlock_minimum_reboiler(self):
        """Flooding interlock should not reduce reboiler below 0.3 MW."""
        x_next = {
            "dP_col": 0.335,
            "T_top": 85.0,
            "xB_sd": 0.9995,
            "L_Drum": 0.5,
        }
        u_applied = {"SP_F_Reflux": 25.0, "SP_F_Reboil": 0.4, "SP_F_ToTol": 55.0}

        result = safety_logic(x_next, u_applied)

        # Should be max(0.4 - 0.2, 0.3) = 0.3
        assert result["adjust"]["SP_F_Reboil"] == 0.3

    def test_flooding_interlock_increases_reflux(self):
        """Flooding interlock should increase reflux by 2.0 t/h."""
        x_next = {
            "dP_col": 0.335,
            "T_top": 85.0,
            "xB_sd": 0.9995,
            "L_Drum": 0.5,
        }
        u_applied = {"SP_F_Reflux": 30.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}

        result = safety_logic(x_next, u_applied)

        # Should increase reflux by 2.0 t/h
        expected_reflux = 30.0 + 2.0  # = 32.0
        assert result["adjust"]["SP_F_Reflux"] == expected_reflux

    def test_flooding_interlock_maximum_reflux(self):
        """Flooding interlock should not increase reflux beyond 45.0 t/h."""
        x_next = {
            "dP_col": 0.335,
            "T_top": 85.0,
            "xB_sd": 0.9995,
            "L_Drum": 0.5,
        }
        u_applied = {"SP_F_Reflux": 44.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}

        result = safety_logic(x_next, u_applied)

        # Should be min(44.0 + 2.0, 45.0) = 45.0
        assert result["adjust"]["SP_F_Reflux"] == 45.0

    def test_no_interlock_below_trip_threshold(self):
        """Interlock should not trigger below trip threshold."""
        x_next = {
            "dP_col": 0.32,  # Below trip threshold (0.33)
            "T_top": 85.0,
            "xB_sd": 0.9995,
            "L_Drum": 0.5,
        }
        u_applied = {"SP_F_Reflux": 25.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}

        result = safety_logic(x_next, u_applied)

        assert len(result["interlock"]) == 0
        assert len(result["adjust"]) == 0


class TestEmergencyShutdown:
    """Test emergency shutdown (ESD) triggers."""

    def test_esd_critical_dp(self):
        """Critical ΔP should trigger ESD."""
        x_next = {
            "dP_col": 0.35,  # Above ESD threshold (0.34)
            "T_top": 85.0,
            "xB_sd": 0.9995,
            "L_Drum": 0.5,
        }
        u_applied = {"SP_F_Reflux": 25.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}

        result = safety_logic(x_next, u_applied)

        assert result["esd"] is True

    def test_esd_critical_temperature(self):
        """Critical overhead temperature should trigger ESD."""
        x_next = {
            "dP_col": 0.15,
            "T_top": 104.0,  # Above ESD threshold (103.0)
            "xB_sd": 0.9995,
            "L_Drum": 0.5,
        }
        u_applied = {"SP_F_Reflux": 25.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}

        result = safety_logic(x_next, u_applied)

        assert result["esd"] is True

    def test_esd_critical_drum_level(self):
        """Critical low drum level should trigger ESD."""
        x_next = {
            "dP_col": 0.15,
            "T_top": 85.0,
            "xB_sd": 0.9995,
            "L_Drum": 0.04,  # Below critical threshold (0.05)
        }
        u_applied = {"SP_F_Reflux": 25.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}

        result = safety_logic(x_next, u_applied)

        assert result["esd"] is True

    def test_esd_boundary_conditions(self):
        """Test ESD at exact threshold boundaries."""
        # At threshold - should NOT trigger (> not >=)
        x_next = {
            "dP_col": 0.34,  # Exactly at threshold
            "T_top": 103.0,  # Exactly at threshold
            "xB_sd": 0.9995,
            "L_Drum": 0.05,  # Exactly at threshold
        }
        u_applied = {"SP_F_Reflux": 25.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}

        result = safety_logic(x_next, u_applied)

        # At exact threshold, ESD should NOT trigger (requires >)
        assert result["esd"] is False

        # Just above threshold - should trigger
        x_next["dP_col"] = 0.3401
        result = safety_logic(x_next, u_applied)
        assert result["esd"] is True

    def test_no_esd_normal_operation(self):
        """Normal operation should not trigger ESD."""
        x_next = {
            "dP_col": 0.15,
            "T_top": 85.0,
            "xB_sd": 0.9995,
            "L_Drum": 0.5,
        }
        u_applied = {"SP_F_Reflux": 25.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}

        result = safety_logic(x_next, u_applied)

        assert result["esd"] is False

    def test_esd_missing_drum_level(self):
        """Missing drum level should use default (0.5) and not trigger ESD."""
        x_next = {
            "dP_col": 0.15,
            "T_top": 85.0,
            "xB_sd": 0.9995,
            # L_Drum intentionally missing
        }
        u_applied = {"SP_F_Reflux": 25.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}

        result = safety_logic(x_next, u_applied)

        assert result["esd"] is False


class TestMoveRateLimits:
    """Test move rate limiting to prevent dangerous control changes."""

    def test_reflux_rate_limit_increase(self):
        """Reflux changes should be limited to +2.0 t/h per turn."""
        x_curr = {"F_Reflux": 25.0, "F_Reboil": 1.2, "F_ToTol": 55.0}
        u_req = {"SP_F_Reflux": 30.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}

        result = cap_moves(u_req, x_curr)

        # Should be capped at 25.0 + 2.0 = 27.0
        assert result["SP_F_Reflux"] == 27.0

    def test_reflux_rate_limit_decrease(self):
        """Reflux changes should be limited to -2.0 t/h per turn."""
        x_curr = {"F_Reflux": 25.0, "F_Reboil": 1.2, "F_ToTol": 55.0}
        u_req = {"SP_F_Reflux": 20.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}

        result = cap_moves(u_req, x_curr)

        # Should be capped at 25.0 - 2.0 = 23.0
        assert result["SP_F_Reflux"] == 23.0

    def test_reboiler_rate_limit_increase(self):
        """Reboiler changes should be limited to +0.15 MW per turn."""
        x_curr = {"F_Reflux": 25.0, "F_Reboil": 1.2, "F_ToTol": 55.0}
        u_req = {"SP_F_Reflux": 25.0, "SP_F_Reboil": 2.0, "SP_F_ToTol": 55.0}

        result = cap_moves(u_req, x_curr)

        # Should be capped at 1.2 + 0.15 = 1.35
        assert result["SP_F_Reboil"] == pytest.approx(1.35)

    def test_reboiler_rate_limit_decrease(self):
        """Reboiler changes should be limited to -0.15 MW per turn."""
        x_curr = {"F_Reflux": 25.0, "F_Reboil": 1.2, "F_ToTol": 55.0}
        u_req = {"SP_F_Reflux": 25.0, "SP_F_Reboil": 0.5, "SP_F_ToTol": 55.0}

        result = cap_moves(u_req, x_curr)

        # Should be capped at 1.2 - 0.15 = 1.05
        assert result["SP_F_Reboil"] == 1.05

    def test_totol_rate_limit_increase(self):
        """Toluene transfer changes should be limited to +5.0 t/h per turn."""
        x_curr = {"F_Reflux": 25.0, "F_Reboil": 1.2, "F_ToTol": 55.0}
        u_req = {"SP_F_Reflux": 25.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 70.0}

        result = cap_moves(u_req, x_curr)

        # Should be capped at 55.0 + 5.0 = 60.0
        assert result["SP_F_ToTol"] == 60.0

    def test_totol_rate_limit_decrease(self):
        """Toluene transfer changes should be limited to -5.0 t/h per turn."""
        x_curr = {"F_Reflux": 25.0, "F_Reboil": 1.2, "F_ToTol": 55.0}
        u_req = {"SP_F_Reflux": 25.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 40.0}

        result = cap_moves(u_req, x_curr)

        # Should be capped at 55.0 - 5.0 = 50.0
        assert result["SP_F_ToTol"] == 50.0

    def test_multiple_rate_limits(self):
        """Multiple simultaneous rate limits should all be applied."""
        x_curr = {"F_Reflux": 25.0, "F_Reboil": 1.2, "F_ToTol": 55.0}
        u_req = {"SP_F_Reflux": 35.0, "SP_F_Reboil": 2.5, "SP_F_ToTol": 70.0}

        result = cap_moves(u_req, x_curr)

        assert result["SP_F_Reflux"] == 27.0  # 25.0 + 2.0
        assert result["SP_F_Reboil"] == pytest.approx(1.35)  # 1.2 + 0.15
        assert result["SP_F_ToTol"] == 60.0  # 55.0 + 5.0

    def test_no_rate_limit_within_bounds(self):
        """Small changes within rate limits should pass through unchanged."""
        x_curr = {"F_Reflux": 25.0, "F_Reboil": 1.2, "F_ToTol": 55.0}
        u_req = {"SP_F_Reflux": 26.0, "SP_F_Reboil": 1.3, "SP_F_ToTol": 57.0}

        result = cap_moves(u_req, x_curr)

        assert result["SP_F_Reflux"] == 26.0
        assert result["SP_F_Reboil"] == 1.3
        assert result["SP_F_ToTol"] == 57.0


class TestSafetySystemIntegration:
    """Test interactions between different safety tiers."""

    def test_alarm_and_interlock_together(self):
        """Alarms and interlocks can trigger simultaneously."""
        x_next = {
            "dP_col": 0.335,  # Triggers both alarm and interlock
            "T_top": 101.0,  # Triggers alarm
            "xB_sd": 0.9995,
            "L_Drum": 0.5,
        }
        u_applied = {"SP_F_Reflux": 25.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}

        result = safety_logic(x_next, u_applied)

        assert "High column ΔP" in result["alarms"]
        assert "High overhead T" in result["alarms"]
        assert len(result["interlock"]) > 0
        assert result["esd"] is False

    def test_all_three_tiers_active(self):
        """All three safety tiers can be active simultaneously."""
        x_next = {
            "dP_col": 0.35,  # Triggers alarm, interlock, AND ESD
            "T_top": 104.0,  # Triggers alarm AND ESD
            "xB_sd": 0.9985,  # Triggers alarm
            "L_Drum": 0.08,  # Triggers alarm
        }
        u_applied = {"SP_F_Reflux": 25.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}

        result = safety_logic(x_next, u_applied)

        assert len(result["alarms"]) >= 2
        assert len(result["interlock"]) > 0
        assert result["esd"] is True

    def test_safety_hierarchy_thresholds(self):
        """Verify correct threshold hierarchy: alarm < interlock < ESD."""
        # For ΔP
        assert LIMITS["dP_alarm"] < LIMITS["dP_trip"] < LIMITS["dP_esd"]

        # For temperature
        assert LIMITS["T_top_alarm"] < LIMITS["T_top_esd"]

        # For drum level
        assert LIMITS["L_drum_crit"] < LIMITS["L_drum_min"]
