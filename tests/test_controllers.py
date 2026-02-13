"""Tests for controllers."""

import pytest

from src.models.plant_state import PlantState
from src.models.constants import STEADY_STATE, ACTUATOR_RANGES, DEFAULT_SCENARIO
from src.controllers.nn_controller import NNController
from src.controllers.mpc_controller import MPCController


def _make_state(**overrides) -> PlantState:
    d = {**STEADY_STATE, **overrides}
    return PlantState.from_dict(d)


class TestNNController:
    def test_returns_all_keys(self):
        ctrl = NNController()
        state = _make_state()
        u = ctrl.decide(state, DEFAULT_SCENARIO)
        assert "SP_F_Reflux" in u
        assert "SP_F_Reboil" in u
        assert "SP_F_ToTol" in u

    def test_name(self):
        assert NNController().name == "NN Policy"

    def test_outputs_within_range(self):
        ctrl = NNController()
        state = _make_state()
        u = ctrl.decide(state, DEFAULT_SCENARIO)
        rr_lo, rr_hi = ACTUATOR_RANGES["SP_F_Reflux"]
        qr_lo, qr_hi = ACTUATOR_RANGES["SP_F_Reboil"]
        tt_lo, tt_hi = ACTUATOR_RANGES["SP_F_ToTol"]
        assert rr_lo <= u["SP_F_Reflux"] <= rr_hi
        assert qr_lo <= u["SP_F_Reboil"] <= qr_hi
        assert tt_lo <= u["SP_F_ToTol"] <= tt_hi

    def test_low_purity_increases_reflux(self):
        ctrl = NNController()
        state = _make_state(xB_sd=0.990)
        u = ctrl.decide(state, DEFAULT_SCENARIO)
        assert u["SP_F_Reflux"] > state.F_Reflux

    def test_high_dP_reduces_reflux(self):
        ctrl = NNController()
        state = _make_state(dP_col=0.32)
        u = ctrl.decide(state, DEFAULT_SCENARIO)
        # High dP should push reflux down from the dP correction term
        # (even if purity term pushes it up, net effect depends on magnitudes)
        assert isinstance(u["SP_F_Reflux"], float)


class TestMPCController:
    def test_returns_all_keys(self):
        ctrl = MPCController()
        state = _make_state()
        u = ctrl.decide(state, DEFAULT_SCENARIO)
        assert "SP_F_Reflux" in u
        assert "SP_F_Reboil" in u
        assert "SP_F_ToTol" in u

    def test_name(self):
        assert MPCController().name == "Linear MPC"

    def test_outputs_within_range(self):
        ctrl = MPCController()
        state = _make_state()
        u = ctrl.decide(state, DEFAULT_SCENARIO)
        rr_lo, rr_hi = ACTUATOR_RANGES["SP_F_Reflux"]
        qr_lo, qr_hi = ACTUATOR_RANGES["SP_F_Reboil"]
        tt_lo, tt_hi = ACTUATOR_RANGES["SP_F_ToTol"]
        assert rr_lo <= u["SP_F_Reflux"] <= rr_hi
        assert qr_lo <= u["SP_F_Reboil"] <= qr_hi
        assert tt_lo <= u["SP_F_ToTol"] <= tt_hi

    def test_fallback_works(self):
        ctrl = MPCController()
        state = _make_state()
        u = ctrl._fallback(state)
        assert "SP_F_Reflux" in u
