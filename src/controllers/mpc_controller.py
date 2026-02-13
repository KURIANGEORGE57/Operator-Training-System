"""Linear Model Predictive Controller (2x2).

Controls reflux flow and reboiler duty to track benzene purity and column
differential pressure targets. Uses CVXPY for quadratic programming.
"""

from __future__ import annotations

from typing import Dict

import numpy as np

from src.controllers.base import Controller
from src.models.constants import LIMITS, ACTUATOR_RANGES, MOVE_CAPS
from src.models.plant_state import PlantState

try:
    import cvxpy as cp

    _HAVE_CVXPY = True
except ImportError:
    _HAVE_CVXPY = False


class MPCController(Controller):
    """2x2 linear MPC: (reflux, reboil) -> (xB, dP)."""

    HORIZON = 15

    # Linearized discrete plant model around steady state
    A = np.array([[1.0, 0.0], [0.0, 1.0]])
    B = np.array([[0.005, 0.004], [0.003, -0.001]])
    C = np.eye(2)

    # Cost weights
    Q = np.diag([2000.0, 50.0])   # Output tracking (purity >> pressure)
    R = np.diag([0.0, 0.0])       # Control effort
    S = np.diag([1.0, 1.0])       # Move suppression

    @property
    def name(self) -> str:
        return "Linear MPC"

    def decide(
        self,
        state: PlantState,
        scenario: Dict[str, float],
    ) -> Dict[str, float]:
        if not _HAVE_CVXPY:
            return self._fallback(state)

        N = self.HORIZON
        nx, nu = 2, 2

        # Decision variables
        x = cp.Variable((nx, N + 1))
        u = cp.Variable((nu, N))

        # References and initial conditions
        x0 = np.array([state.xB_sd, state.dP_col])
        ref = np.array([LIMITS.xB_spec, 0.10])

        # Control bounds
        u_lo = np.array([ACTUATOR_RANGES["SP_F_Reflux"][0], ACTUATOR_RANGES["SP_F_Reboil"][0]])
        u_hi = np.array([ACTUATOR_RANGES["SP_F_Reflux"][1], ACTUATOR_RANGES["SP_F_Reboil"][1]])
        du_max = np.array([MOVE_CAPS["SP_F_Reflux"], MOVE_CAPS["SP_F_Reboil"]])

        # Current actuator values as initial u
        u_prev = np.array([state.F_Reflux, state.F_Reboil])

        cost = 0.0
        constraints = [x[:, 0] == x0]

        for k in range(N):
            y_k = self.C @ x[:, k]
            cost += cp.quad_form(y_k - ref, self.Q)
            cost += cp.quad_form(u[:, k], self.R)

            if k == 0:
                cost += cp.quad_form(u[:, k] - u_prev, self.S)
            else:
                cost += cp.quad_form(u[:, k] - u[:, k - 1], self.S)

            constraints += [
                x[:, k + 1] == self.A @ x[:, k] + self.B @ u[:, k],
                u[:, k] >= u_lo,
                u[:, k] <= u_hi,
            ]

            if k == 0:
                constraints += [
                    u[:, k] - u_prev <= du_max,
                    u[:, k] - u_prev >= -du_max,
                ]
            else:
                constraints += [
                    u[:, k] - u[:, k - 1] <= du_max,
                    u[:, k] - u[:, k - 1] >= -du_max,
                ]

        prob = cp.Problem(cp.Minimize(cost), constraints)
        try:
            prob.solve(solver=cp.OSQP, warm_start=True, verbose=False)
            if prob.status in ("optimal", "optimal_inaccurate"):
                reflux_opt = float(u.value[0, 0])
                reboil_opt = float(u.value[1, 0])
            else:
                return self._fallback(state)
        except Exception:
            return self._fallback(state)

        return {
            "SP_F_Reflux": reflux_opt,
            "SP_F_Reboil": reboil_opt,
            "SP_F_ToTol": state.F_ToTol,
        }

    def _fallback(self, state: PlantState) -> Dict[str, float]:
        """Simple proportional fallback if CVXPY is unavailable."""
        xB_err = LIMITS.xB_spec - state.xB_sd
        return {
            "SP_F_Reflux": float(np.clip(state.F_Reflux + 3.0 * xB_err, *ACTUATOR_RANGES["SP_F_Reflux"])),
            "SP_F_Reboil": float(np.clip(state.F_Reboil + 1.5 * xB_err, *ACTUATOR_RANGES["SP_F_Reboil"])),
            "SP_F_ToTol": state.F_ToTol,
        }
