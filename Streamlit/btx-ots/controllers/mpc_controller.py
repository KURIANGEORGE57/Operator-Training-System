import numpy as np
import cvxpy as cp
from typing import Dict

from logger import get_logger


LOGGER = get_logger(__name__)

class ControllerMPC:
    """
    2×2 Linear MPC (reflux, reboil) -> (purity, dP).
    Replace A,B,C,D with your identified/linearized model for best results.
    """

    def __init__(self, horizon: int = 15):
        # Example discrete model (toy)
        self.A = np.array([[1.0,  0.0],
                           [0.0,  1.0]])
        self.B = np.array([[0.005, 0.004],
                           [0.003, -0.001]])
        self.C = np.eye(2); self.D = np.zeros((2,2))
        self.N = horizon

        nx, nu, ny = 2, 2, 2
        self.x = cp.Variable((nx, self.N+1))
        self.u = cp.Variable((nu, self.N))
        self.y = cp.Variable((ny, self.N))

        # Parameters
        self.x0  = cp.Parameter(nx)  # [xB, dP]
        self.r   = cp.Parameter(ny)  # [xB_target, dP_target]
        self.u0  = cp.Parameter(nu)  # last inputs
        self.u_lo = cp.Parameter(nu)
        self.u_hi = cp.Parameter(nu)
        self.du_max = cp.Parameter(nu)

        Q = np.diag([2000.0, 50.0])  # prioritize purity
        R = np.diag([0.0, 0.0])
        S = np.diag([1.0, 1.0])      # move suppression

        constr = [self.x[:,0] == self.x0]
        cost = 0
        for k in range(self.N):
            constr += [self.x[:,k+1] == self.A @ self.x[:,k] + self.B @ self.u[:,k]]
            yk = self.C @ self.x[:,k] + self.D @ self.u[:,k]
            constr += [self.y[:,k] == yk]
            constr += [self.u[:,k] >= self.u_lo, self.u[:,k] <= self.u_hi]
            if k == 0:
                constr += [cp.abs(self.u[:,k] - self.u0) <= self.du_max]
            else:
                constr += [cp.abs(self.u[:,k] - self.u[:,k-1]) <= self.du_max]
            cost += cp.quad_form(yk - self.r, Q) + cp.quad_form(self.u[:,k], R)
            if k == 0:
                cost += cp.quad_form(self.u[:,k] - self.u0, S)
            else:
                cost += cp.quad_form(self.u[:,k] - self.u[:,k-1], S)

        self.prob = cp.Problem(cp.Minimize(cost), constr)

    def decide(self, state: Dict, scenario: Dict, limits: Dict) -> Dict:
        xB = state["xB_sd"]; dP = state["dP_col"]
        rr_last = state["F_Reflux"]; qreb_last = state["F_Reboil"]

        xB_target = limits.get("xB_spec", 0.9990)
        dP_target = min(limits.get("dP_max", 0.30), 0.20)

        r_lo, r_hi = limits["reflux"]
        q_lo, q_hi = limits["reboil"]
        du_max = np.array([2.5, 0.15])  # per turn caps

        self.x0.value = np.array([xB, dP])
        self.r.value = np.array([xB_target, dP_target])
        self.u0.value = np.array([rr_last, qreb_last])
        self.u_lo.value = np.array([r_lo, q_lo])
        self.u_hi.value = np.array([r_hi, q_hi])
        self.du_max.value = du_max

        try:
            self.prob.solve(solver=cp.OSQP, warm_start=True, eps_abs=1e-4, eps_rel=1e-4, max_iter=4000)
        except cp.SolverError as exc:
            LOGGER.warning("MPC solver raised %s; falling back to previous setpoints: %s", type(exc).__name__, exc)
            status = "solver_error"
            u0_value = None
        else:
            status = self.prob.status
            u0_value = self.u[:,0].value

        if status not in {cp.OPTIMAL, cp.OPTIMAL_INACCURATE} or u0_value is None:
            LOGGER.warning("MPC solver returned status %s with u0=%s; using previous setpoints.", status, u0_value)
            u0 = np.array([rr_last, qreb_last], dtype=float)
        else:
            u0 = u0_value

        rr = float(np.clip(u0[0], r_lo, r_hi))
        qreb = float(np.clip(u0[1], q_lo, q_hi))
        totol = float(state["F_ToTol"])  # leave transfer flow unchanged
        return {"SP_F_Reflux": rr, "SP_F_Reboil": qreb, "SP_F_ToTol": totol}
