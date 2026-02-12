"""Lightweight heuristic benzene column stub (fallback / reference).

Simpler than PlantNeqSim — uses linear sensitivities instead of VLE.
Kept for environments where NeqSim is unavailable.
"""

import numpy as np
from typing import Dict

from plant_base import PlantBase


class Plant(PlantBase):

    def __init__(self) -> None:
        super().__init__()
        self.state = {
            "xB_sd":    0.9950,
            "dP_col":   0.08,
            "T_top":    85.0,
            "L_Drum":   0.65,
            "L_Bot":    0.55,
            "F_Reflux": 25.0,
            "F_Reboil": 1.20,
            "F_ToTol":  55.0,
        }

    @staticmethod
    def _clip(name: str, val: float) -> float:
        bounds = {
            "xB_sd":    (0.95, 0.9999),
            "dP_col":   (0.02, 0.40),
            "T_top":    (60.0, 110.0),
            "L_Drum":   (0.0, 1.0),
            "L_Bot":    (0.0, 1.0),
            "F_Reflux": (10.0, 45.0),
            "F_Reboil": (0.3, 3.5),
            "F_ToTol":  (30.0, 90.0),
        }
        lo, hi = bounds[name]
        return float(np.clip(val, lo, hi))

    def physics_step(self, x: Dict, u: Dict, sc: Dict) -> Dict:
        rr = u["SP_F_Reflux"]
        qreb = u["SP_F_Reboil"]
        totol = u["SP_F_ToTol"]
        feed = sc["F_feed"]
        zB = sc["zB_feed"]
        fC = sc["Fouling_Cond"]
        fR = sc["Fouling_Reb"]

        xn = dict(x)

        # Inventory
        xn["L_Drum"] = self._clip(
            "L_Drum",
            x["L_Drum"] + 0.001 * (rr - x["F_Reflux"]) - 0.0005 * (totol - 55) + 0.0004 * (feed - 80),
        )
        xn["L_Bot"] = self._clip(
            "L_Bot",
            x["L_Bot"] + 0.0006 * (feed - 80) - 0.0007 * (totol - 55) - 0.0003 * (qreb - 1.2),
        )

        # Actuator tracking (first-order lag)
        xn["F_Reflux"] = self._clip("F_Reflux", x["F_Reflux"] + 0.4 * (rr - x["F_Reflux"]))
        xn["F_Reboil"] = self._clip("F_Reboil", x["F_Reboil"] + 0.4 * (qreb - x["F_Reboil"]))
        xn["F_ToTol"] = self._clip("F_ToTol", x["F_ToTol"] + 0.4 * (totol - x["F_ToTol"]))

        # Quality / hydraulics heuristics
        xn["xB_sd"] = self._clip(
            "xB_sd",
            x["xB_sd"]
            + 0.0015 * (rr - 25) / 5
            + 0.0012 * (qreb - 1.2)
            + 0.001 * (zB - 0.60) / 0.05
            - 0.0025 * fC
            - 0.0020 * fR
            - 0.001 * (feed - 80) / 40
            - 0.0008 * (x["dP_col"] - 0.08) / 0.1,
        )
        xn["dP_col"] = self._clip(
            "dP_col",
            x["dP_col"]
            + 0.015 * fC
            + 0.012 * (feed - 80) / 40
            + 0.004 * (rr - 25) / 10
            - 0.003 * (totol - 55) / 10,
        )
        xn["T_top"] = self._clip(
            "T_top",
            x["T_top"]
            + 0.18 * (feed - 80) / 40
            - 0.12 * (rr - 25) / 10
            + 0.14 * fC
            + 0.08 * fR,
        )
        return xn

    def step(self, u: Dict, scenario: Dict) -> Dict:
        return self.physics_step(self.state, u, scenario)

    def commit(self, x_next: Dict) -> None:
        self.state = dict(x_next)

    def esd_safe_state(self) -> None:
        self.state.update({
            "F_Reflux": 20.0,
            "F_Reboil": 0.5,
            "F_ToTol":  40.0,
            "xB_sd":    max(self.state["xB_sd"] - 0.001, 0.95),
            "dP_col":   min(self.state["dP_col"], 0.28),
            "T_top":    self._clip("T_top", self.state.get("T_top", 90.0) - 5.0),
            "L_Drum":   max(self.state.get("L_Drum", 0.5), 0.20),
            "L_Bot":    max(self.state.get("L_Bot", 0.5), 0.20),
        })
