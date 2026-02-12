"""Unit tests for the three-tier safety system (alarms, interlocks, ESD)
and the per-turn move-rate limiter.

Run:  pytest test_safety.py -v
"""

import pytest
import numpy as np
from typing import Dict

# ═══════════════════════════════════════════════════════════════════════════
# Duplicate safety constants + functions here so tests run standalone
# without importing Streamlit (which requires a running event loop).
# ═══════════════════════════════════════════════════════════════════════════

LIMITS = {
    "dP_alarm":    0.30,
    "dP_trip":     0.33,
    "dP_esd":      0.34,
    "T_top_alarm": 100.0,
    "T_top_esd":   103.0,
    "xB_spec":     0.9990,
    "L_drum_min":  0.10,
    "L_drum_crit": 0.05,
}


def cap_moves(u_req: Dict, x_curr: Dict) -> Dict:
    caps = {"SP_F_Reflux": 2.0, "SP_F_Reboil": 0.15, "SP_F_ToTol": 5.0}
    u = u_req.copy()
    u["SP_F_Reflux"] = float(np.clip(u["SP_F_Reflux"], x_curr["F_Reflux"] - caps["SP_F_Reflux"], x_curr["F_Reflux"] + caps["SP_F_Reflux"]))
    u["SP_F_Reboil"] = float(np.clip(u["SP_F_Reboil"], x_curr["F_Reboil"] - caps["SP_F_Reboil"], x_curr["F_Reboil"] + caps["SP_F_Reboil"]))
    u["SP_F_ToTol"]  = float(np.clip(u["SP_F_ToTol"],  x_curr["F_ToTol"]  - caps["SP_F_ToTol"],  x_curr["F_ToTol"]  + caps["SP_F_ToTol"]))
    return u


def safety_logic(x_next: Dict, u_applied: Dict) -> Dict:
    alarms, interlock = [], []
    adjust: Dict[str, float] = {}
    esd = False

    if x_next["dP_col"] > LIMITS["dP_alarm"]:
        alarms.append("High column ΔP")
    if x_next["T_top"] > LIMITS["T_top_alarm"]:
        alarms.append("High overhead T")
    if x_next["xB_sd"] < LIMITS["xB_spec"]:
        alarms.append("Off-spec benzene purity")
    if x_next.get("L_Drum", 0.5) < LIMITS["L_drum_min"]:
        alarms.append("Low reflux drum level")

    if x_next["dP_col"] > LIMITS["dP_trip"]:
        interlock.append("Flooding ILK: clamp reboil, increase reflux")
        adjust["SP_F_Reboil"] = max(u_applied["SP_F_Reboil"] - 0.2, 0.3)
        adjust["SP_F_Reflux"] = min(u_applied["SP_F_Reflux"] + 2.0, 45.0)

    if (
        x_next["dP_col"] > LIMITS["dP_esd"]
        or x_next["T_top"] > LIMITS["T_top_esd"]
        or x_next.get("L_Drum", 0.5) < LIMITS["L_drum_crit"]
    ):
        esd = True

    return {"alarms": alarms, "interlock": interlock, "adjust": adjust, "esd": esd}


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _normal_state():
    return {"dP_col": 0.15, "T_top": 85.0, "xB_sd": 0.9995, "L_Drum": 0.5}

def _normal_u():
    return {"SP_F_Reflux": 25.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}


# ═══════════════════════════════════════════════════════════════════════════
# Alarm tests
# ═══════════════════════════════════════════════════════════════════════════

class TestAlarms:

    def test_high_column_dp_alarm(self):
        x = {**_normal_state(), "dP_col": 0.31}
        r = safety_logic(x, _normal_u())
        assert "High column ΔP" in r["alarms"]
        assert not r["esd"]

    def test_high_overhead_temp_alarm(self):
        x = {**_normal_state(), "T_top": 101.0}
        r = safety_logic(x, _normal_u())
        assert "High overhead T" in r["alarms"]
        assert not r["esd"]

    def test_off_spec_benzene_purity_alarm(self):
        x = {**_normal_state(), "xB_sd": 0.9985}
        r = safety_logic(x, _normal_u())
        assert "Off-spec benzene purity" in r["alarms"]
        assert not r["esd"]

    def test_low_drum_level_alarm(self):
        x = {**_normal_state(), "L_Drum": 0.08}
        r = safety_logic(x, _normal_u())
        assert "Low reflux drum level" in r["alarms"]
        assert not r["esd"]

    def test_multiple_alarms(self):
        x = {"dP_col": 0.31, "T_top": 101.0, "xB_sd": 0.9985, "L_Drum": 0.08}
        r = safety_logic(x, _normal_u())
        assert len(r["alarms"]) == 4

    def test_no_alarms_normal_operation(self):
        r = safety_logic(_normal_state(), _normal_u())
        assert len(r["alarms"]) == 0
        assert not r["esd"]


# ═══════════════════════════════════════════════════════════════════════════
# Interlock tests
# ═══════════════════════════════════════════════════════════════════════════

class TestInterlocks:

    def test_flooding_interlock_triggers(self):
        x = {**_normal_state(), "dP_col": 0.335}
        r = safety_logic(x, _normal_u())
        assert len(r["interlock"]) == 1
        assert "Flooding ILK" in r["interlock"][0]
        assert "SP_F_Reboil" in r["adjust"]
        assert "SP_F_Reflux" in r["adjust"]

    def test_flooding_interlock_reduces_reboiler(self):
        x = {**_normal_state(), "dP_col": 0.335}
        u = {**_normal_u(), "SP_F_Reboil": 1.5}
        r = safety_logic(x, u)
        assert r["adjust"]["SP_F_Reboil"] == 1.3  # 1.5 - 0.2

    def test_flooding_interlock_minimum_reboiler(self):
        x = {**_normal_state(), "dP_col": 0.335}
        u = {**_normal_u(), "SP_F_Reboil": 0.4}
        r = safety_logic(x, u)
        assert r["adjust"]["SP_F_Reboil"] == 0.3  # max(0.4 - 0.2, 0.3)

    def test_flooding_interlock_increases_reflux(self):
        x = {**_normal_state(), "dP_col": 0.335}
        u = {**_normal_u(), "SP_F_Reflux": 30.0}
        r = safety_logic(x, u)
        assert r["adjust"]["SP_F_Reflux"] == 32.0  # 30 + 2

    def test_flooding_interlock_maximum_reflux(self):
        x = {**_normal_state(), "dP_col": 0.335}
        u = {**_normal_u(), "SP_F_Reflux": 44.0}
        r = safety_logic(x, u)
        assert r["adjust"]["SP_F_Reflux"] == 45.0  # min(44 + 2, 45)

    def test_no_interlock_below_trip_threshold(self):
        x = {**_normal_state(), "dP_col": 0.32}
        r = safety_logic(x, _normal_u())
        assert len(r["interlock"]) == 0
        assert len(r["adjust"]) == 0


# ═══════════════════════════════════════════════════════════════════════════
# ESD tests
# ═══════════════════════════════════════════════════════════════════════════

class TestEmergencyShutdown:

    def test_esd_critical_dp(self):
        x = {**_normal_state(), "dP_col": 0.35}
        assert safety_logic(x, _normal_u())["esd"] is True

    def test_esd_critical_temperature(self):
        x = {**_normal_state(), "T_top": 104.0}
        assert safety_logic(x, _normal_u())["esd"] is True

    def test_esd_critical_drum_level(self):
        x = {**_normal_state(), "L_Drum": 0.04}
        assert safety_logic(x, _normal_u())["esd"] is True

    def test_esd_boundary_conditions(self):
        # Exactly at threshold → should NOT trigger (uses >)
        x = {"dP_col": 0.34, "T_top": 103.0, "xB_sd": 0.9995, "L_Drum": 0.05}
        assert safety_logic(x, _normal_u())["esd"] is False

        # Just above → should trigger
        x["dP_col"] = 0.3401
        assert safety_logic(x, _normal_u())["esd"] is True

    def test_no_esd_normal_operation(self):
        assert safety_logic(_normal_state(), _normal_u())["esd"] is False

    def test_esd_missing_drum_level(self):
        x = {"dP_col": 0.15, "T_top": 85.0, "xB_sd": 0.9995}  # no L_Drum
        assert safety_logic(x, _normal_u())["esd"] is False


# ═══════════════════════════════════════════════════════════════════════════
# Rate-limit tests
# ═══════════════════════════════════════════════════════════════════════════

class TestMoveRateLimits:

    _X = {"F_Reflux": 25.0, "F_Reboil": 1.2, "F_ToTol": 55.0}

    def test_reflux_rate_limit_increase(self):
        r = cap_moves({"SP_F_Reflux": 30.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}, self._X)
        assert r["SP_F_Reflux"] == 27.0

    def test_reflux_rate_limit_decrease(self):
        r = cap_moves({"SP_F_Reflux": 20.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}, self._X)
        assert r["SP_F_Reflux"] == 23.0

    def test_reboiler_rate_limit_increase(self):
        r = cap_moves({"SP_F_Reflux": 25.0, "SP_F_Reboil": 2.0, "SP_F_ToTol": 55.0}, self._X)
        assert r["SP_F_Reboil"] == pytest.approx(1.35)

    def test_reboiler_rate_limit_decrease(self):
        r = cap_moves({"SP_F_Reflux": 25.0, "SP_F_Reboil": 0.5, "SP_F_ToTol": 55.0}, self._X)
        assert r["SP_F_Reboil"] == 1.05

    def test_totol_rate_limit_increase(self):
        r = cap_moves({"SP_F_Reflux": 25.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 70.0}, self._X)
        assert r["SP_F_ToTol"] == 60.0

    def test_totol_rate_limit_decrease(self):
        r = cap_moves({"SP_F_Reflux": 25.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 40.0}, self._X)
        assert r["SP_F_ToTol"] == 50.0

    def test_multiple_rate_limits(self):
        r = cap_moves({"SP_F_Reflux": 35.0, "SP_F_Reboil": 2.5, "SP_F_ToTol": 70.0}, self._X)
        assert r["SP_F_Reflux"] == 27.0
        assert r["SP_F_Reboil"] == pytest.approx(1.35)
        assert r["SP_F_ToTol"] == 60.0

    def test_no_rate_limit_within_bounds(self):
        r = cap_moves({"SP_F_Reflux": 26.0, "SP_F_Reboil": 1.3, "SP_F_ToTol": 57.0}, self._X)
        assert r["SP_F_Reflux"] == 26.0
        assert r["SP_F_Reboil"] == 1.3
        assert r["SP_F_ToTol"] == 57.0


# ═══════════════════════════════════════════════════════════════════════════
# Integration tests
# ═══════════════════════════════════════════════════════════════════════════

class TestSafetySystemIntegration:

    def test_alarm_and_interlock_together(self):
        x = {"dP_col": 0.335, "T_top": 101.0, "xB_sd": 0.9995, "L_Drum": 0.5}
        r = safety_logic(x, _normal_u())
        assert "High column ΔP" in r["alarms"]
        assert "High overhead T" in r["alarms"]
        assert len(r["interlock"]) > 0
        assert r["esd"] is False

    def test_all_three_tiers_active(self):
        x = {"dP_col": 0.35, "T_top": 104.0, "xB_sd": 0.9985, "L_Drum": 0.08}
        r = safety_logic(x, _normal_u())
        assert len(r["alarms"]) >= 2
        assert len(r["interlock"]) > 0
        assert r["esd"] is True

    def test_safety_hierarchy_thresholds(self):
        assert LIMITS["dP_alarm"] < LIMITS["dP_trip"] < LIMITS["dP_esd"]
        assert LIMITS["T_top_alarm"] < LIMITS["T_top_esd"]
        assert LIMITS["L_drum_crit"] < LIMITS["L_drum_min"]
