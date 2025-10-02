import numpy as np
from typing import Dict

class Plant:
    """
    Tiny, stable stub of a benzene column "plant".
    Replace physics_step() with your NN surrogate or DWSIM-backed service.
    """
    def __init__(self):
        self.state = {
            "xB_sd": 0.9950,   # benzene purity side-draw
            "dP_col": 0.08,    # bar
            "T_top": 85.0,     # °C
            "L_Drum": 0.65,    # 0..1
            "L_Bot":  0.55,    # 0..1
            "F_Reflux": 25.0,  # t/h (actual)
            "F_Reboil": 1.20,  # MW eq. (proxy)
            "F_ToTol":  55.0,  # t/h
        }

    def _clip(self, name, val):
        bounds = {
            "xB_sd": (0.95, 0.9999),
            "dP_col": (0.02, 0.40),
            "T_top": (60.0, 110.0),
            "L_Drum": (0.0, 1.0),
            "L_Bot": (0.0, 1.0),
            "F_Reflux": (10.0, 45.0),
            "F_Reboil": (0.3, 3.5),
            "F_ToTol": (30.0, 90.0),
        }
        lo, hi = bounds[name]
        return float(np.clip(val, lo, hi))

    def physics_step(self, x: Dict, u: Dict, sc: Dict) -> Dict:
        """
        Simple discrete-time update capturing intuitive trends only.
        Replace with your trained NN: x_next = model.predict([x,u,sc]).
        """
        rr = u["SP_F_Reflux"]
        qreb = u["SP_F_Reboil"]
        totol = u["SP_F_ToTol"]
        feed = sc["F_feed"]
        zB = sc["zB_feed"]
        fC = sc["Fouling_Cond"]
        fR = sc["Fouling_Reb"]

        x_next = dict(x)

        # Inventory effects (toy)
        x_next["L_Drum"] = self._clip("L_Drum", x["L_Drum"] + 0.001*(rr - x["F_Reflux"]) - 0.0005*(totol-55) + 0.0004*(feed-80))
        x_next["L_Bot"]  = self._clip("L_Bot",  x["L_Bot"]  + 0.0006*(feed-80) - 0.0007*(totol-55) - 0.0003*(qreb-1.2))

        # Actuator tracking (first-order lag to SPs)
        x_next["F_Reflux"] = self._clip("F_Reflux", x["F_Reflux"] + 0.4*(rr - x["F_Reflux"]))
        x_next["F_Reboil"] = self._clip("F_Reboil", x["F_Reboil"] + 0.4*(qreb - x["F_Reboil"]))
        x_next["F_ToTol"]  = self._clip("F_ToTol",  x["F_ToTol"]  + 0.4*(totol - x["F_ToTol"]))

        # Quality / hydraulics heuristics (toy)
        x_next["xB_sd"] = self._clip("xB_sd",
            x["xB_sd"] + 0.0015*(rr-25)/5 + 0.0012*(qreb-1.2) + 0.001*(zB-0.60)/0.05
            - 0.0025*fC - 0.0020*fR - 0.001*(feed-80)/40 - 0.0008*(x["dP_col"]-0.08)/0.1
        )
        x_next["dP_col"] = self._clip("dP_col",
            x["dP_col"] + 0.015*fC + 0.012*(feed-80)/40 + 0.004*(rr-25)/10 - 0.003*(totol-55)/10
        )
        x_next["T_top"] = self._clip("T_top",
            x["T_top"] + 0.18*(feed-80)/40 - 0.12*(rr-25)/10 + 0.14*fC + 0.08*fR
        )
        return x_next

    def step(self, u: Dict, scenario: Dict) -> Dict:
        """Compute tentative next state (no commit)."""
        return self.physics_step(self.state, u, scenario)

    def commit(self, x_next: Dict):
        self.state = x_next

    def esd_safe_state(self):
        # Simple safe state
        self.state.update({
            "F_Reflux": 20.0,
            "F_Reboil": 0.5,
            "F_ToTol": 40.0,
            "xB_sd": max(self.state["xB_sd"] - 0.001, 0.95),
            "dP_col": min(self.state["dP_col"], 0.28),
        })
