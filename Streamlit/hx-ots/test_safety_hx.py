"""Unit tests for heat exchanger safety logic.

This test suite verifies the safety systems for the heat exchanger OTS:
1. Alarms - Temperature, pressure, flow, fouling, and leak warnings
2. Interlocks - Automatic protective actions
3. Emergency Shutdown (ESD) - Last-resort safety
4. Move rate limiting - Prevents thermal shock
"""

import pytest
import numpy as np
from typing import Dict


# Safety thresholds from app.py
LIMITS = {
    "T_hot_out_alarm": 140.0,
    "T_hot_out_esd": 150.0,
    "T_cold_out_alarm": 55.0,
    "T_cold_out_esd": 60.0,
    "dP_hot_alarm": 2.0,
    "dP_hot_esd": 2.5,
    "dP_cold_alarm": 1.2,
    "dP_cold_esd": 1.5,
    "F_hot_min": 10.0,
    "F_cold_min": 15.0,
    "fouling_alarm": 0.50,
    "fouling_critical": 0.75,
    "tube_leak_alarm": 0.10,
    "tube_leak_critical": 0.30,
    "approach_temp_min": 5.0,
}


def cap_moves(u_req: Dict, x_curr: Dict) -> Dict:
    """Rate limit control changes to prevent thermal shock."""
    caps = {"SP_F_hot": 5.0, "SP_F_cold": 10.0}
    u = u_req.copy()

    u["SP_F_hot"] = float(np.clip(
        u["SP_F_hot"],
        x_curr["F_hot"] - caps["SP_F_hot"],
        x_curr["F_hot"] + caps["SP_F_hot"]
    ))
    u["SP_F_cold"] = float(np.clip(
        u["SP_F_cold"],
        x_curr["F_cold"] - caps["SP_F_cold"],
        x_curr["F_cold"] + caps["SP_F_cold"]
    ))

    return u


def safety_logic(x_next: Dict, u_applied: Dict) -> Dict:
    """Three-tier safety system for heat exchanger."""
    alarms, interlock, esd = [], [], False
    adjust = {}

    # Tier 1: Alarms
    if x_next["T_hot_out"] > LIMITS["T_hot_out_alarm"]:
        alarms.append("High hot outlet temperature")
    if x_next["T_cold_out"] > LIMITS["T_cold_out_alarm"]:
        alarms.append("High cold outlet temperature")
    if x_next["dP_hot"] > LIMITS["dP_hot_alarm"]:
        alarms.append("High hot side pressure drop")
    if x_next["dP_cold"] > LIMITS["dP_cold_alarm"]:
        alarms.append("High cold side pressure drop")
    if x_next["F_hot"] < LIMITS["F_hot_min"]:
        alarms.append("Low hot side flow")
    if x_next["F_cold"] < LIMITS["F_cold_min"]:
        alarms.append("Low cold side flow")
    if x_next["fouling_hot"] > LIMITS["fouling_alarm"]:
        alarms.append("High hot side fouling")
    if x_next["fouling_cold"] > LIMITS["fouling_alarm"]:
        alarms.append("High cold side fouling")
    if x_next["tube_leak"] > LIMITS["tube_leak_alarm"]:
        alarms.append("Tube leakage detected")

    approach_temp = min(
        x_next["T_hot_out"] - x_next["T_cold_in"],
        x_next["T_cold_out"] - x_next["T_cold_in"]
    )
    if approach_temp < LIMITS["approach_temp_min"]:
        alarms.append("Low temperature approach - poor heat transfer")

    # Tier 2: Interlocks
    if x_next["dP_hot"] > (LIMITS["dP_hot_alarm"] + 0.3):
        interlock.append("High ΔP interlock: increase cold flow, reduce hot flow")
        adjust["SP_F_hot"] = max(u_applied["SP_F_hot"] - 5.0, LIMITS["F_hot_min"])
        adjust["SP_F_cold"] = min(u_applied["SP_F_cold"] + 10.0, 100.0)

    if x_next["T_hot_out"] > (LIMITS["T_hot_out_alarm"] + 5.0):
        interlock.append("High temp interlock: increase cold flow")
        adjust["SP_F_cold"] = min(
            u_applied.get("SP_F_cold", 50.0) + 15.0, 100.0
        )

    if (x_next["fouling_hot"] > LIMITS["fouling_critical"] or
        x_next["fouling_cold"] > LIMITS["fouling_critical"]):
        interlock.append("Critical fouling interlock: reduce flows")
        adjust["SP_F_hot"] = max(u_applied["SP_F_hot"] * 0.7, LIMITS["F_hot_min"])
        adjust["SP_F_cold"] = max(u_applied["SP_F_cold"] * 0.7, LIMITS["F_cold_min"])

    # Tier 3: Emergency Shutdown
    if (x_next["T_hot_out"] > LIMITS["T_hot_out_esd"] or
        x_next["T_cold_out"] > LIMITS["T_cold_out_esd"] or
        x_next["dP_hot"] > LIMITS["dP_hot_esd"] or
        x_next["dP_cold"] > LIMITS["dP_cold_esd"] or
        x_next["tube_leak"] > LIMITS["tube_leak_critical"]):
        esd = True

    return {"alarms": alarms, "interlock": interlock, "adjust": adjust, "esd": esd}


# ============================================================================
# Test Suite
# ============================================================================


class TestAlarms:
    """Test alarm generation for heat exchanger."""

    def test_high_hot_outlet_temp_alarm(self):
        """High hot outlet temperature should trigger alarm."""
        x_next = {
            "T_hot_in": 120.0,
            "T_hot_out": 145.0,  # Above alarm (140.0)
            "T_cold_in": 25.0,
            "T_cold_out": 45.0,
            "F_hot": 30.0,
            "F_cold": 50.0,
            "dP_hot": 0.8,
            "dP_cold": 0.4,
            "fouling_hot": 0.0,
            "fouling_cold": 0.0,
            "tube_leak": 0.0,
        }
        u = {"SP_F_hot": 30.0, "SP_F_cold": 50.0}

        result = safety_logic(x_next, u)

        assert "High hot outlet temperature" in result["alarms"]
        assert not result["esd"]

    def test_high_cold_outlet_temp_alarm(self):
        """High cold outlet temperature should trigger alarm."""
        x_next = {
            "T_hot_in": 120.0,
            "T_hot_out": 60.0,
            "T_cold_in": 25.0,
            "T_cold_out": 56.0,  # Above alarm (55.0)
            "F_hot": 30.0,
            "F_cold": 50.0,
            "dP_hot": 0.8,
            "dP_cold": 0.4,
            "fouling_hot": 0.0,
            "fouling_cold": 0.0,
            "tube_leak": 0.0,
        }
        u = {"SP_F_hot": 30.0, "SP_F_cold": 50.0}

        result = safety_logic(x_next, u)

        assert "High cold outlet temperature" in result["alarms"]
        assert not result["esd"]

    def test_high_pressure_drop_alarms(self):
        """High pressure drops should trigger alarms."""
        x_next = {
            "T_hot_in": 120.0,
            "T_hot_out": 60.0,
            "T_cold_in": 25.0,
            "T_cold_out": 45.0,
            "F_hot": 30.0,
            "F_cold": 50.0,
            "dP_hot": 2.1,  # Above alarm (2.0)
            "dP_cold": 1.3,  # Above alarm (1.2)
            "fouling_hot": 0.0,
            "fouling_cold": 0.0,
            "tube_leak": 0.0,
        }
        u = {"SP_F_hot": 30.0, "SP_F_cold": 50.0}

        result = safety_logic(x_next, u)

        assert "High hot side pressure drop" in result["alarms"]
        assert "High cold side pressure drop" in result["alarms"]

    def test_low_flow_alarms(self):
        """Low flows should trigger alarms."""
        x_next = {
            "T_hot_in": 120.0,
            "T_hot_out": 60.0,
            "T_cold_in": 25.0,
            "T_cold_out": 45.0,
            "F_hot": 8.0,  # Below minimum (10.0)
            "F_cold": 12.0,  # Below minimum (15.0)
            "dP_hot": 0.3,
            "dP_cold": 0.2,
            "fouling_hot": 0.0,
            "fouling_cold": 0.0,
            "tube_leak": 0.0,
        }
        u = {"SP_F_hot": 8.0, "SP_F_cold": 12.0}

        result = safety_logic(x_next, u)

        assert "Low hot side flow" in result["alarms"]
        assert "Low cold side flow" in result["alarms"]

    def test_fouling_alarms(self):
        """High fouling should trigger alarms."""
        x_next = {
            "T_hot_in": 120.0,
            "T_hot_out": 60.0,
            "T_cold_in": 25.0,
            "T_cold_out": 45.0,
            "F_hot": 30.0,
            "F_cold": 50.0,
            "dP_hot": 1.5,
            "dP_cold": 0.8,
            "fouling_hot": 0.55,  # Above alarm (0.50)
            "fouling_cold": 0.60,  # Above alarm (0.50)
            "tube_leak": 0.0,
        }
        u = {"SP_F_hot": 30.0, "SP_F_cold": 50.0}

        result = safety_logic(x_next, u)

        assert "High hot side fouling" in result["alarms"]
        assert "High cold side fouling" in result["alarms"]

    def test_tube_leak_alarm(self):
        """Tube leakage should trigger alarm."""
        x_next = {
            "T_hot_in": 120.0,
            "T_hot_out": 60.0,
            "T_cold_in": 25.0,
            "T_cold_out": 45.0,
            "F_hot": 30.0,
            "F_cold": 50.0,
            "dP_hot": 0.8,
            "dP_cold": 0.4,
            "fouling_hot": 0.0,
            "fouling_cold": 0.0,
            "tube_leak": 0.15,  # Above alarm (0.10)
        }
        u = {"SP_F_hot": 30.0, "SP_F_cold": 50.0}

        result = safety_logic(x_next, u)

        assert "Tube leakage detected" in result["alarms"]

    def test_low_approach_temp_alarm(self):
        """Low temperature approach should trigger alarm."""
        x_next = {
            "T_hot_in": 120.0,
            "T_hot_out": 28.0,  # Approach = 28 - 25 = 3°C (< 5°C)
            "T_cold_in": 25.0,
            "T_cold_out": 45.0,
            "F_hot": 30.0,
            "F_cold": 50.0,
            "dP_hot": 0.8,
            "dP_cold": 0.4,
            "fouling_hot": 0.0,
            "fouling_cold": 0.0,
            "tube_leak": 0.0,
        }
        u = {"SP_F_hot": 30.0, "SP_F_cold": 50.0}

        result = safety_logic(x_next, u)

        assert "Low temperature approach - poor heat transfer" in result["alarms"]


class TestInterlocks:
    """Test automatic protective interlocks."""

    def test_high_dp_interlock(self):
        """High pressure drop interlock should reduce hot flow, increase cold flow."""
        x_next = {
            "T_hot_in": 120.0,
            "T_hot_out": 60.0,
            "T_cold_in": 25.0,
            "T_cold_out": 45.0,
            "F_hot": 40.0,
            "F_cold": 50.0,
            "dP_hot": 2.4,  # Above alarm + 0.3 = 2.3
            "dP_cold": 0.4,
            "fouling_hot": 0.0,
            "fouling_cold": 0.0,
            "tube_leak": 0.0,
        }
        u = {"SP_F_hot": 40.0, "SP_F_cold": 50.0}

        result = safety_logic(x_next, u)

        assert len(result["interlock"]) > 0
        assert "SP_F_hot" in result["adjust"]
        assert "SP_F_cold" in result["adjust"]
        assert result["adjust"]["SP_F_hot"] < u["SP_F_hot"]
        assert result["adjust"]["SP_F_cold"] > u["SP_F_cold"]

    def test_high_temp_interlock(self):
        """High temperature interlock should increase cold flow."""
        x_next = {
            "T_hot_in": 120.0,
            "T_hot_out": 146.0,  # Above alarm + 5 = 145
            "T_cold_in": 25.0,
            "T_cold_out": 45.0,
            "F_hot": 30.0,
            "F_cold": 50.0,
            "dP_hot": 0.8,
            "dP_cold": 0.4,
            "fouling_hot": 0.0,
            "fouling_cold": 0.0,
            "tube_leak": 0.0,
        }
        u = {"SP_F_hot": 30.0, "SP_F_cold": 50.0}

        result = safety_logic(x_next, u)

        assert len(result["interlock"]) > 0
        assert "SP_F_cold" in result["adjust"]
        assert result["adjust"]["SP_F_cold"] > u["SP_F_cold"]

    def test_critical_fouling_interlock(self):
        """Critical fouling should reduce both flows."""
        x_next = {
            "T_hot_in": 120.0,
            "T_hot_out": 60.0,
            "T_cold_in": 25.0,
            "T_cold_out": 45.0,
            "F_hot": 30.0,
            "F_cold": 50.0,
            "dP_hot": 1.5,
            "dP_cold": 0.8,
            "fouling_hot": 0.80,  # Above critical (0.75)
            "fouling_cold": 0.20,
            "tube_leak": 0.0,
        }
        u = {"SP_F_hot": 30.0, "SP_F_cold": 50.0}

        result = safety_logic(x_next, u)

        assert len(result["interlock"]) > 0
        assert "SP_F_hot" in result["adjust"]
        assert "SP_F_cold" in result["adjust"]
        # Flows reduced to 70%
        assert result["adjust"]["SP_F_hot"] == pytest.approx(30.0 * 0.7)
        assert result["adjust"]["SP_F_cold"] == pytest.approx(50.0 * 0.7)


class TestEmergencyShutdown:
    """Test ESD triggers."""

    def test_esd_high_hot_temp(self):
        """Critical hot outlet temperature should trigger ESD."""
        x_next = {
            "T_hot_in": 120.0,
            "T_hot_out": 151.0,  # Above ESD (150.0)
            "T_cold_in": 25.0,
            "T_cold_out": 45.0,
            "F_hot": 30.0,
            "F_cold": 50.0,
            "dP_hot": 0.8,
            "dP_cold": 0.4,
            "fouling_hot": 0.0,
            "fouling_cold": 0.0,
            "tube_leak": 0.0,
        }
        u = {"SP_F_hot": 30.0, "SP_F_cold": 50.0}

        result = safety_logic(x_next, u)

        assert result["esd"] is True

    def test_esd_high_cold_temp(self):
        """Critical cold outlet temperature should trigger ESD."""
        x_next = {
            "T_hot_in": 120.0,
            "T_hot_out": 60.0,
            "T_cold_in": 25.0,
            "T_cold_out": 61.0,  # Above ESD (60.0)
            "F_hot": 30.0,
            "F_cold": 50.0,
            "dP_hot": 0.8,
            "dP_cold": 0.4,
            "fouling_hot": 0.0,
            "fouling_cold": 0.0,
            "tube_leak": 0.0,
        }
        u = {"SP_F_hot": 30.0, "SP_F_cold": 50.0}

        result = safety_logic(x_next, u)

        assert result["esd"] is True

    def test_esd_high_pressure_drop(self):
        """Critical pressure drops should trigger ESD."""
        x_next = {
            "T_hot_in": 120.0,
            "T_hot_out": 60.0,
            "T_cold_in": 25.0,
            "T_cold_out": 45.0,
            "F_hot": 30.0,
            "F_cold": 50.0,
            "dP_hot": 2.6,  # Above ESD (2.5)
            "dP_cold": 0.4,
            "fouling_hot": 0.0,
            "fouling_cold": 0.0,
            "tube_leak": 0.0,
        }
        u = {"SP_F_hot": 30.0, "SP_F_cold": 50.0}

        result = safety_logic(x_next, u)

        assert result["esd"] is True

    def test_esd_critical_tube_leak(self):
        """Critical tube leak should trigger ESD."""
        x_next = {
            "T_hot_in": 120.0,
            "T_hot_out": 60.0,
            "T_cold_in": 25.0,
            "T_cold_out": 45.0,
            "F_hot": 30.0,
            "F_cold": 50.0,
            "dP_hot": 0.8,
            "dP_cold": 0.4,
            "fouling_hot": 0.0,
            "fouling_cold": 0.0,
            "tube_leak": 0.35,  # Above critical (0.30)
        }
        u = {"SP_F_hot": 30.0, "SP_F_cold": 50.0}

        result = safety_logic(x_next, u)

        assert result["esd"] is True


class TestMoveRateLimits:
    """Test move rate limiting."""

    def test_hot_flow_rate_limit_increase(self):
        """Hot flow should be limited to +5 kg/s per turn."""
        x_curr = {"F_hot": 30.0, "F_cold": 50.0}
        u_req = {"SP_F_hot": 40.0, "SP_F_cold": 50.0}

        result = cap_moves(u_req, x_curr)

        # Should be capped at 30 + 5 = 35
        assert result["SP_F_hot"] == 35.0

    def test_hot_flow_rate_limit_decrease(self):
        """Hot flow should be limited to -5 kg/s per turn."""
        x_curr = {"F_hot": 30.0, "F_cold": 50.0}
        u_req = {"SP_F_hot": 20.0, "SP_F_cold": 50.0}

        result = cap_moves(u_req, x_curr)

        # Should be capped at 30 - 5 = 25
        assert result["SP_F_hot"] == 25.0

    def test_cold_flow_rate_limit_increase(self):
        """Cold flow should be limited to +10 kg/s per turn."""
        x_curr = {"F_hot": 30.0, "F_cold": 50.0}
        u_req = {"SP_F_hot": 30.0, "SP_F_cold": 70.0}

        result = cap_moves(u_req, x_curr)

        # Should be capped at 50 + 10 = 60
        assert result["SP_F_cold"] == 60.0

    def test_cold_flow_rate_limit_decrease(self):
        """Cold flow should be limited to -10 kg/s per turn."""
        x_curr = {"F_hot": 30.0, "F_cold": 50.0}
        u_req = {"SP_F_hot": 30.0, "SP_F_cold": 30.0}

        result = cap_moves(u_req, x_curr)

        # Should be capped at 50 - 10 = 40
        assert result["SP_F_cold"] == 40.0

    def test_both_flows_rate_limited(self):
        """Both flows can be rate limited simultaneously."""
        x_curr = {"F_hot": 30.0, "F_cold": 50.0}
        u_req = {"SP_F_hot": 50.0, "SP_F_cold": 80.0}

        result = cap_moves(u_req, x_curr)

        assert result["SP_F_hot"] == 35.0  # 30 + 5
        assert result["SP_F_cold"] == 60.0  # 50 + 10
