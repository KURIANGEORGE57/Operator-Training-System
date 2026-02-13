"""Neural-network-style heuristic controller.

Uses proportional-derivative-like heuristics as a stand-in for a trained
neural network policy. The control logic targets benzene purity specification
while respecting column pressure constraints.
"""

from __future__ import annotations

from typing import Dict

import numpy as np

from src.controllers.base import Controller
from src.models.constants import LIMITS, ACTUATOR_RANGES
from src.models.plant_state import PlantState


class NNController(Controller):
    """Heuristic controller mimicking a trained NN policy."""

    @property
    def name(self) -> str:
        return "NN Policy"

    def decide(
        self,
        state: PlantState,
        scenario: Dict[str, float],
    ) -> Dict[str, float]:
        xB_target = LIMITS.xB_spec
        dP_limit = LIMITS.dP_alarm

        xB_err = xB_target - state.xB_sd
        dP_excess = max(0.0, state.dP_col - dP_limit)

        # Reflux: increase for purity, decrease for pressure
        reflux = state.F_Reflux + 5.0 * xB_err - 3.0 * dP_excess
        rr_lo, rr_hi = ACTUATOR_RANGES["SP_F_Reflux"]
        reflux = float(np.clip(reflux, rr_lo, rr_hi))

        # Reboiler: increase for purity, decrease for pressure
        reboil = state.F_Reboil + 2.0 * xB_err - 1.0 * dP_excess
        qr_lo, qr_hi = ACTUATOR_RANGES["SP_F_Reboil"]
        reboil = float(np.clip(reboil, qr_lo, qr_hi))

        # Toluene transfer: maintain current flow
        totol = state.F_ToTol
        tt_lo, tt_hi = ACTUATOR_RANGES["SP_F_ToTol"]
        totol = float(np.clip(totol, tt_lo, tt_hi))

        return {
            "SP_F_Reflux": reflux,
            "SP_F_Reboil": reboil,
            "SP_F_ToTol": totol,
        }
