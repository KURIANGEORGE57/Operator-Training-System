"""2x2 Linear MPC controller: (reflux, reboil) -> (purity, dP).

Uses CVXPY + OSQP for the quadratic program.  Replace A, B, C, D with
an identified / linearised model for production use.
"""

import numpy as np
import cvxpy as cp
from typing import Dict


class ControllerMPC:

    def __init__(self, horizon: int = 15) -> None:
        self.N = horizon
        nx, nu, ny = 2, 2, 2

        # Toy discrete state-space model
        self.A = np.eye(nx)
        self.B = np.array([[0.005, 0.004],
                           [0.003, -0.001]])
        self.C = np.eye(ny)
        self.D = np.zeros((ny, nu))

        # CVXPY variables
        self.x = cp.Variable((nx, self.N + 1))
        self.u = cp.Variable((nu, self.N))
        self.y = cp.Variable((ny, self.N))

        # Parameters (set at solve time)
        self.x0 = cp.Parameter(nx)
        self.r = cp.Parameter(ny)
        self.u0 = cp.Parameter(nu)
        self.u_lo = cp.Parameter(nu)
        self.u_hi = cp.Parameter(nu)
        self.du_max = cp.Parameter(nu)

        # Cost weights
        Q = np.diag([2000.0, 50.0])  # purity >> dP
        R = np.diag([0.0, 0.0])
        S = np.diag([1.0, 1.0])      # move suppression

        constr = [self.x[:, 0] == self.x0]
        cost = 0
        for k in range(self.N):
            constr += [self.x[:, k + 1] == self.A @ self.x[:, k] + self.B @ self.u[:, k]]
            yk = self.C @ self.x[:, k] + self.D @ self.u[:, k]
            constr += [self.y[:, k] == yk]
            constr += [self.u[:, k] >= self.u_lo, self.u[:, k] <= self.u_hi]

            u_prev = self.u0 if k == 0 else self.u[:, k - 1]
            constr += [cp.abs(self.u[:, k] - u_prev) <= self.du_max]
            cost += cp.quad_form(yk - self.r, Q) + cp.quad_form(self.u[:, k], R)
            cost += cp.quad_form(self.u[:, k] - u_prev, S)

        self.prob = cp.Problem(cp.Minimize(cost), constr)

    def decide(self, state: Dict, scenario: Dict, limits: Dict) -> Dict:
        xB = state["xB_sd"]
        dP = state["dP_col"]
        rr_last = state["F_Reflux"]
        qreb_last = state["F_Reboil"]

        xB_target = limits.get("xB_spec", 0.9990)
        dP_target = min(limits.get("dP_max", 0.30), 0.20)

        r_lo, r_hi = limits["reflux"]
        q_lo, q_hi = limits["reboil"]

        self.x0.value = np.array([xB, dP])
        self.r.value = np.array([xB_target, dP_target])
        self.u0.value = np.array([rr_last, qreb_last])
        self.u_lo.value = np.array([r_lo, q_lo])
        self.u_hi.value = np.array([r_hi, q_hi])
        self.du_max.value = np.array([2.5, 0.15])

        self.prob.solve(solver=cp.OSQP, warm_start=True, eps_abs=1e-4, eps_rel=1e-4, max_iter=4000)

        u0 = self.u[:, 0].value
        rr = float(np.clip(u0[0], r_lo, r_hi))
        qreb = float(np.clip(u0[1], q_lo, q_hi))
        totol = float(state["F_ToTol"])  # leave transfer unchanged

        return {"SP_F_Reflux": rr, "SP_F_Reboil": qreb, "SP_F_ToTol": totol}
