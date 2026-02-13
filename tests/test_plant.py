"""Tests for plant model physics and state management."""

import pytest

from src.models.plant import Plant, cap_moves
from src.models.plant_state import PlantState
from src.models.constants import STEADY_STATE, MOVE_CAPS, DEFAULT_SCENARIO


class TestPlantState:
    """PlantState dataclass operations."""

    def test_to_dict_roundtrip(self):
        state = PlantState(**STEADY_STATE)
        d = state.to_dict()
        restored = PlantState.from_dict(d)
        assert restored == state

    def test_from_dict_ignores_extra_keys(self):
        d = {**STEADY_STATE, "extra_key": 999}
        state = PlantState.from_dict(d)
        assert state.xB_sd == STEADY_STATE["xB_sd"]

    def test_immutability(self):
        state = PlantState(**STEADY_STATE)
        with pytest.raises(AttributeError):
            state.xB_sd = 0.5


class TestPlantInit:
    """Plant initialization."""

    def test_default_state(self):
        plant = Plant()
        assert plant.state.xB_sd == STEADY_STATE["xB_sd"]
        assert plant.state.F_Reflux == STEADY_STATE["F_Reflux"]

    def test_custom_initial_state(self):
        custom = {**STEADY_STATE, "xB_sd": 0.99}
        plant = Plant(initial_state=custom)
        assert plant.state.xB_sd == 0.99


class TestPlantStep:
    """Plant step (tentative state computation)."""

    def test_step_does_not_mutate_state(self):
        plant = Plant()
        original = plant.state
        u = {"SP_F_Reflux": 30.0, "SP_F_Reboil": 1.5, "SP_F_ToTol": 60.0}
        plant.step(u, DEFAULT_SCENARIO)
        assert plant.state == original

    def test_step_returns_plant_state(self):
        plant = Plant()
        u = {"SP_F_Reflux": 25.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}
        result = plant.step(u, DEFAULT_SCENARIO)
        assert isinstance(result, PlantState)

    def test_increasing_reboil_raises_purity(self):
        plant = Plant()
        u_base = {"SP_F_Reflux": 25.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}
        u_high = {"SP_F_Reflux": 25.0, "SP_F_Reboil": 2.5, "SP_F_ToTol": 55.0}
        x_base = plant.step(u_base, DEFAULT_SCENARIO)
        x_high = plant.step(u_high, DEFAULT_SCENARIO)
        assert x_high.xB_sd > x_base.xB_sd

    def test_increasing_reflux_raises_purity(self):
        plant = Plant()
        u_base = {"SP_F_Reflux": 20.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}
        u_high = {"SP_F_Reflux": 40.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}
        x_base = plant.step(u_base, DEFAULT_SCENARIO)
        x_high = plant.step(u_high, DEFAULT_SCENARIO)
        assert x_high.xB_sd > x_base.xB_sd

    def test_fouling_increases_dP(self):
        plant = Plant()
        u = {"SP_F_Reflux": 25.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}
        sc_clean = {**DEFAULT_SCENARIO, "Fouling_Cond": 0.0, "Fouling_Reb": 0.0}
        sc_fouled = {**DEFAULT_SCENARIO, "Fouling_Cond": 0.5, "Fouling_Reb": 0.5}
        x_clean = plant.step(u, sc_clean)
        x_fouled = plant.step(u, sc_fouled)
        assert x_fouled.dP_col > x_clean.dP_col

    def test_levels_stay_bounded(self):
        plant = Plant()
        u = {"SP_F_Reflux": 45.0, "SP_F_Reboil": 3.5, "SP_F_ToTol": 90.0}
        for _ in range(50):
            x = plant.step(u, DEFAULT_SCENARIO)
            plant.commit(x)
        assert 0.0 <= plant.state.L_Drum <= 1.0
        assert 0.0 <= plant.state.L_Bot <= 1.0


class TestPlantCommit:
    """Plant commit (state acceptance)."""

    def test_commit_updates_state(self):
        plant = Plant()
        u = {"SP_F_Reflux": 30.0, "SP_F_Reboil": 1.5, "SP_F_ToTol": 60.0}
        x_next = plant.step(u, DEFAULT_SCENARIO)
        plant.commit(x_next)
        assert plant.state == x_next

    def test_esd_sets_conservative_values(self):
        plant = Plant()
        safe = plant.esd_safe_state()
        assert safe.F_Reflux == 20.0
        assert safe.F_Reboil == 0.5
        assert safe.F_ToTol == 45.0
        assert safe.dP_col <= 0.25


class TestCapMoves:
    """Move rate limiting."""

    def test_reflux_capped_up(self):
        state = PlantState(**STEADY_STATE)
        u = {"SP_F_Reflux": 40.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}
        capped = cap_moves(u, state)
        assert capped["SP_F_Reflux"] == pytest.approx(
            state.F_Reflux + MOVE_CAPS["SP_F_Reflux"]
        )

    def test_reflux_capped_down(self):
        state = PlantState(**STEADY_STATE)
        u = {"SP_F_Reflux": 10.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}
        capped = cap_moves(u, state)
        assert capped["SP_F_Reflux"] == pytest.approx(
            state.F_Reflux - MOVE_CAPS["SP_F_Reflux"]
        )

    def test_reboil_capped(self):
        state = PlantState(**STEADY_STATE)
        u = {"SP_F_Reflux": 25.0, "SP_F_Reboil": 3.5, "SP_F_ToTol": 55.0}
        capped = cap_moves(u, state)
        assert capped["SP_F_Reboil"] == pytest.approx(
            state.F_Reboil + MOVE_CAPS["SP_F_Reboil"]
        )

    def test_transfer_capped(self):
        state = PlantState(**STEADY_STATE)
        u = {"SP_F_Reflux": 25.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 90.0}
        capped = cap_moves(u, state)
        assert capped["SP_F_ToTol"] == pytest.approx(
            state.F_ToTol + MOVE_CAPS["SP_F_ToTol"]
        )

    def test_small_move_not_capped(self):
        state = PlantState(**STEADY_STATE)
        u = {"SP_F_Reflux": 25.5, "SP_F_Reboil": 1.25, "SP_F_ToTol": 56.0}
        capped = cap_moves(u, state)
        assert capped["SP_F_Reflux"] == pytest.approx(25.5)
        assert capped["SP_F_Reboil"] == pytest.approx(1.25)
        assert capped["SP_F_ToTol"] == pytest.approx(56.0)

    def test_all_moves_capped_simultaneously(self):
        state = PlantState(**STEADY_STATE)
        u = {"SP_F_Reflux": 45.0, "SP_F_Reboil": 3.5, "SP_F_ToTol": 90.0}
        capped = cap_moves(u, state)
        for sp_key, pv_key in [
            ("SP_F_Reflux", "F_Reflux"),
            ("SP_F_Reboil", "F_Reboil"),
            ("SP_F_ToTol", "F_ToTol"),
        ]:
            diff = abs(capped[sp_key] - state.to_dict()[pv_key])
            assert diff <= MOVE_CAPS[sp_key] + 1e-9
