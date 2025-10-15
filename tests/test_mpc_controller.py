import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

try:
    import cvxpy as cp
except ModuleNotFoundError:  # pragma: no cover - exercised in CI without cvxpy
    cp = None  # type: ignore[assignment]


if cp is not None:  # pragma: no branch - conditional import for optional dependency
    MODULE_PATH = Path(__file__).resolve().parents[1] / "Streamlit" / "btx-ots" / "controllers" / "mpc_controller.py"
    spec = importlib.util.spec_from_file_location("mpc_controller", MODULE_PATH)
    mpc_module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mpc_module
    assert spec.loader is not None
    spec.loader.exec_module(mpc_module)
    ControllerMPC = mpc_module.ControllerMPC
else:
    ControllerMPC = None


@unittest.skipIf(ControllerMPC is None, "cvxpy not available")
class ControllerMPCTest(unittest.TestCase):
    def setUp(self) -> None:
        self.controller = ControllerMPC()
        self.state = {
            "xB_sd": 0.98,
            "dP_col": 0.12,
            "F_Reflux": 5.0,
            "F_Reboil": 1.6,
            "F_ToTol": 0.3,
        }
        self.scenario = {}
        self.limits = {
            "xB_spec": 0.995,
            "dP_max": 0.2,
            "reflux": (2.0, 12.0),
            "reboil": (1.0, 2.5),
        }

    def test_decide_falls_back_when_solver_errors(self) -> None:
        self.controller.prob.solve = Mock(side_effect=cp.SolverError("boom"))

        result = self.controller.decide(self.state, self.scenario, self.limits)

        self.assertAlmostEqual(result["SP_F_Reflux"], self.state["F_Reflux"])
        self.assertAlmostEqual(result["SP_F_Reboil"], self.state["F_Reboil"])
        self.assertAlmostEqual(result["SP_F_ToTol"], self.state["F_ToTol"])

    def test_decide_falls_back_when_status_not_optimal(self) -> None:
        def fake_solve(*_args, **_kwargs):
            self.controller.prob.status = cp.INFEASIBLE
            self.controller.u[:, 0].value = None

        self.controller.prob.solve = fake_solve

        result = self.controller.decide(self.state, self.scenario, self.limits)

        self.assertAlmostEqual(result["SP_F_Reflux"], self.state["F_Reflux"])
        self.assertAlmostEqual(result["SP_F_Reboil"], self.state["F_Reboil"])
        self.assertAlmostEqual(result["SP_F_ToTol"], self.state["F_ToTol"])


if __name__ == "__main__":
    unittest.main()
