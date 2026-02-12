"""Heuristic rule-based controller (placeholder for a trained NN).

Replace decide() with ONNX / PyTorch inference when a trained model
is available.  Returns SP_F_Reflux, SP_F_Reboil, SP_F_ToTol.
"""

import numpy as np
from typing import Dict, Optional


class ControllerNN:

    def __init__(self, model_path: Optional[str] = None) -> None:
        self.model = None  # load trained model here if desired

    def decide(self, state: Dict, scenario: Dict, limits: Dict) -> Dict:
        xB = state["xB_sd"]
        dP = state["dP_col"]
        rr = state["F_Reflux"]
        qreb = state["F_Reboil"]
        totol = state["F_ToTol"]
        xB_target = limits.get("xB_spec", 0.9990)

        # Heuristic nudges as stand-in for learned policy
        rr += 5.0 * (xB_target - xB) - 3.0 * max(0.0, dP - 0.25)
        qreb += 2.0 * (xB_target - xB) - 1.0 * max(0.0, dP - 0.25)

        rr = float(np.clip(rr, *limits["reflux"]))
        qreb = float(np.clip(qreb, *limits["reboil"]))
        totol = float(np.clip(totol, *limits["totol"]))

        return {"SP_F_Reflux": rr, "SP_F_Reboil": qreb, "SP_F_ToTol": totol}
