"""Benzene-toluene distillation column plant model.

Physics-based first-order dynamics with correlation-based thermodynamics.
Implements a two-phase commit pattern: step() computes a tentative next state,
commit() applies it.
"""

from __future__ import annotations

import math
from typing import Dict

import numpy as np

from src.models.plant_state import PlantState
from src.models.constants import STEADY_STATE, MOVE_CAPS


class Plant:
    """Distillation column simulator with first-order dynamics."""

    # Actuator time constants (turns)
    TAU_REFLUX = 0.5
    TAU_REBOIL = 0.5
    TAU_TRANSFER = 0.25

    def __init__(self, initial_state: Dict[str, float] | None = None):
        state = initial_state or dict(STEADY_STATE)
        self._state = PlantState.from_dict(state)

    @property
    def state(self) -> PlantState:
        return self._state

    def step(self, u: Dict[str, float], scenario: Dict[str, float]) -> PlantState:
        """Compute tentative next state without modifying internal state.

        Args:
            u: Control inputs with keys SP_F_Reflux, SP_F_Reboil, SP_F_ToTol.
            scenario: Operating conditions with keys F_feed, zB_feed,
                      Fouling_Cond, Fouling_Reb.

        Returns:
            Tentative PlantState for safety evaluation.
        """
        x = self._state.to_dict()
        return PlantState.from_dict(self._physics(x, u, scenario))

    def commit(self, x_next: PlantState) -> None:
        """Accept a tentative state as the new plant state."""
        self._state = x_next

    def esd_safe_state(self) -> PlantState:
        """Compute and commit a conservative emergency safe state."""
        x = self._state.to_dict()
        safe = {
            "xB_sd": max(x["xB_sd"] - 0.002, 0.90),
            "dP_col": min(x["dP_col"], 0.25),
            "T_top": x["T_top"] - 5.0,
            "L_Drum": min(max(x["L_Drum"], 0.30), 0.70),
            "L_Bot": min(max(x["L_Bot"], 0.30), 0.70),
            "F_Reflux": 20.0,
            "F_Reboil": 0.5,
            "F_ToTol": 45.0,
        }
        self._state = PlantState.from_dict(safe)
        return self._state

    def _physics(
        self, x: Dict[str, float], u: Dict[str, float], sc: Dict[str, float]
    ) -> Dict[str, float]:
        """First-order dynamic model of the benzene column."""
        F_feed = sc.get("F_feed", 80.0)
        zB = sc.get("zB_feed", 0.60)
        foul_c = sc.get("Fouling_Cond", 0.0)
        foul_r = sc.get("Fouling_Reb", 0.0)

        # --- Actuator dynamics: first-order lag toward setpoints ---
        F_Ref = x["F_Reflux"] + (u["SP_F_Reflux"] - x["F_Reflux"]) / (1.0 + self.TAU_REFLUX)
        F_Reb = x["F_Reboil"] + (u["SP_F_Reboil"] - x["F_Reboil"]) / (1.0 + self.TAU_REBOIL)
        F_ToT = x["F_ToTol"] + (u["SP_F_ToTol"] - x["F_ToTol"]) / (1.0 + self.TAU_TRANSFER)

        # --- Level dynamics: mass-balance driven ---
        feed_norm = F_feed / 80.0
        drum_delta = (
            0.02 * (F_Ref - 25.0) / 10.0
            - 0.015 * feed_norm
            + 0.01 * (F_ToT - 55.0) / 20.0
        )
        L_Drum = np.clip(x["L_Drum"] + drum_delta, 0.0, 1.0)

        bot_delta = (
            0.015 * feed_norm
            - 0.02 * (F_ToT - 55.0) / 20.0
            - 0.005 * (F_Reb - 1.2)
        )
        L_Bot = np.clip(x["L_Bot"] + bot_delta, 0.0, 1.0)

        # --- Quality (benzene purity): separation energy balance ---
        separation_energy = (
            0.003 * (F_Ref - 25.0) / 10.0
            + 0.004 * (F_Reb - 1.2)
            - 0.002 * (feed_norm - 1.0)
            - 0.002 * foul_r
            - 0.001 * foul_c
        )
        xB = np.clip(x["xB_sd"] + separation_energy, 0.80, 1.0)

        # --- Column differential pressure: vapor traffic + fouling ---
        dP_base = 0.08
        vapor_traffic = 0.05 * (F_Reb - 1.2) + 0.03 * (F_Ref - 25.0) / 10.0
        fouling_effect = 0.08 * (foul_c + foul_r)
        dP = np.clip(
            x["dP_col"] + 0.3 * (dP_base + vapor_traffic + fouling_effect - x["dP_col"]),
            0.0,
            0.5,
        )

        # --- Overhead temperature: VLE correlation ---
        T_vle = 80.1 + 21.0 * (1.0 - xB) ** 0.85
        fouling_T_bias = 2.0 * foul_c
        T_top = x["T_top"] + 0.4 * (T_vle + fouling_T_bias - x["T_top"])

        return {
            "xB_sd": float(xB),
            "dP_col": float(dP),
            "T_top": float(T_top),
            "L_Drum": float(L_Drum),
            "L_Bot": float(L_Bot),
            "F_Reflux": float(F_Ref),
            "F_Reboil": float(F_Reb),
            "F_ToTol": float(F_ToT),
        }


def cap_moves(
    u_requested: Dict[str, float], current_state: PlantState
) -> Dict[str, float]:
    """Rate-limit control moves to physically realistic magnitudes.

    Prevents dangerous step changes that real actuators cannot achieve.
    """
    x = current_state.to_dict()
    mapping = {
        "SP_F_Reflux": "F_Reflux",
        "SP_F_Reboil": "F_Reboil",
        "SP_F_ToTol": "F_ToTol",
    }
    capped = {}
    for sp_key, pv_key in mapping.items():
        current = x[pv_key]
        requested = u_requested[sp_key]
        cap = MOVE_CAPS[sp_key]
        capped[sp_key] = float(np.clip(requested, current - cap, current + cap))
    return capped
