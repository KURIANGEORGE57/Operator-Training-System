"""Production benzene/toluene column model with optional NeqSim VLE.

First-order dynamics with NeqSim-backed thermodynamics when available,
falling back to smooth correlations otherwise.  Cheap enough for
Streamlit's rerun model while giving realistic response surfaces.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional
import logging

import numpy as np

from plant_base import PlantBase

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional NeqSim import
# ---------------------------------------------------------------------------
try:  # pragma: no cover
    from neqsim.thermo import fluid
    from neqsim.thermo.thermoTools import PHflash, TPflash

    _HAVE_NEQSIM = True
    logger.info("NeqSim loaded successfully")
except ImportError:
    fluid = None  # type: ignore[assignment]
    PHflash = None  # type: ignore[assignment]
    TPflash = None  # type: ignore[assignment]
    _HAVE_NEQSIM = False
    logger.info("NeqSim unavailable — using correlation fallback")
except Exception as exc:
    fluid = None  # type: ignore[assignment]
    PHflash = None  # type: ignore[assignment]
    TPflash = None  # type: ignore[assignment]
    _HAVE_NEQSIM = False
    logger.warning("Unexpected error loading NeqSim (%s)", exc)


# ---------------------------------------------------------------------------
# Column design parameters
# ---------------------------------------------------------------------------
@dataclass
class _ColumnSpec:
    overhead_pressure_bar: float = 1.6
    condenser_duty_tau: float = 0.5   # hours
    reboiler_tau: float = 0.5         # hours
    inventory_tau: float = 0.25       # hours
    feed_temperature_c: float = 95.0
    feed_pressure_bar: float = 2.2


# ---------------------------------------------------------------------------
# Variable bounds
# ---------------------------------------------------------------------------
_BOUNDS = {
    "xB_sd":    (0.90, 0.9999),
    "dP_col":   (0.02, 0.40),
    "T_top":    (60.0, 110.0),
    "L_Drum":   (0.0,  1.0),
    "L_Bot":    (0.0,  1.0),
    "F_Reflux": (10.0, 45.0),
    "F_Reboil": (0.3,  3.5),
    "F_ToTol":  (30.0, 90.0),
}


def _clip(name: str, value: float) -> float:
    lo, hi = _BOUNDS[name]
    return float(np.clip(value, lo, hi))


# ---------------------------------------------------------------------------
# Plant model
# ---------------------------------------------------------------------------
class PlantNeqSim(PlantBase):
    """First-order benzene/toluene column with NeqSim VLE."""

    def __init__(self) -> None:
        super().__init__()
        self.spec = _ColumnSpec()
        self.state = {
            "xB_sd":    0.9950,  # benzene purity (side-draw mol fraction)
            "dP_col":   0.08,    # column differential pressure (bar)
            "T_top":    84.5,    # overhead temperature (deg C)
            "L_Drum":   0.65,    # reflux drum level (0-1)
            "L_Bot":    0.56,    # bottoms level (0-1)
            "F_Reflux": 25.0,    # reflux flow (t/h)
            "F_Reboil": 1.20,    # reboiler duty proxy (MW eq.)
            "F_ToTol":  55.0,    # toluene transfer flow (t/h)
        }
        self._cached_feed: Optional[object] = None
        self._cached_feed_sig: Optional[tuple] = None

    # ---- NeqSim helpers ---------------------------------------------------

    def _make_feed_fluid(self, flow_tph: float, zB: float) -> Optional[object]:
        sig = (round(flow_tph, 1), round(zB, 4))
        if self._cached_feed_sig == sig:
            return self._cached_feed

        if not _HAVE_NEQSIM:
            self._cached_feed = {"zB": zB, "flow": flow_tph}
            self._cached_feed_sig = sig
            return self._cached_feed

        try:
            feed = fluid("srk")  # type: ignore[operator]
            feed.addComponent("benzene", max(zB, 1e-5))
            feed.addComponent("toluene", max(1.0 - zB, 1e-5))
            feed.setMixingRule(2)
            feed.setTemperature(self.spec.feed_temperature_c + 273.15)
            feed.setPressure(self.spec.feed_pressure_bar)
            feed.setTotalFlowRate(max(flow_tph, 1e-3), "kg/hr")
            feed.init(1)
        except Exception as exc:
            logger.warning("NeqSim feed creation failed (%s) — using fallback", exc)
            feed = {"zB": zB, "flow": flow_tph}

        self._cached_feed = feed
        self._cached_feed_sig = sig
        return feed

    def _overhead_T_from_VLE(self, liq_benzene: float, feed_obj: Optional[object]) -> float:
        liq_benzene = float(np.clip(liq_benzene, 1e-4, 0.9999))

        if _HAVE_NEQSIM and feed_obj is not None and not isinstance(feed_obj, dict):
            try:
                top = fluid("srk")  # type: ignore[operator]
                top.addComponent("benzene", liq_benzene)
                top.addComponent("toluene", 1.0 - liq_benzene)
                top.setMixingRule(2)
                top.setTemperature(350.0)  # K initial guess
                top.setPressure(self.spec.overhead_pressure_bar)
                top.init(1)
                TPflash(top)
                return float(top.getTemperature() - 273.15)
            except Exception as exc:
                logger.warning("NeqSim VLE failed (%s) — using fallback", exc)

        # Correlation fallback (benzene BP ~80.1 C, toluene ~110.6 C)
        base = 80.1
        tol_shift = 21.0
        return _clip("T_top", base + tol_shift * (1.0 - liq_benzene) ** 0.85)

    # ---- Physics ----------------------------------------------------------

    def physics_step(
        self, x: Dict[str, float], u: Dict[str, float], sc: Dict[str, float]
    ) -> Dict[str, float]:
        xn = dict(x)

        feed_flow = float(sc.get("F_feed", 80.0))
        feed_zB = float(sc.get("zB_feed", 0.60))
        fouling_cond = float(sc.get("Fouling_Cond", 0.0))
        fouling_reb = float(sc.get("Fouling_Reb", 0.0))

        feed_fluid = self._make_feed_fluid(feed_flow, feed_zB)

        # Actuator tracking — first-order lag to setpoints
        sp_map = {"F_Reflux": "SP_F_Reflux", "F_Reboil": "SP_F_Reboil", "F_ToTol": "SP_F_ToTol"}
        tau_map = {
            "F_Reflux": self.spec.condenser_duty_tau,
            "F_Reboil": self.spec.reboiler_tau,
            "F_ToTol":  self.spec.inventory_tau,
        }
        for key in ("F_Reflux", "F_Reboil", "F_ToTol"):
            tau = tau_map[key]
            delta = u[sp_map[key]] - x[key]
            xn[key] = _clip(key, x[key] + (1.0 - np.exp(-1.0 / tau)) * delta)

        # Level dynamics — mass balance
        reflux_dev = xn["F_Reflux"] - 25.0
        feed_dev = feed_flow - 80.0
        tol_dev = xn["F_ToTol"] - 55.0
        reb_dev = xn["F_Reboil"] - 1.2

        xn["L_Drum"] = _clip(
            "L_Drum",
            x["L_Drum"] + 0.0025 * reflux_dev - 0.0015 * tol_dev + 0.0010 * feed_dev,
        )
        xn["L_Bot"] = _clip(
            "L_Bot",
            x["L_Bot"] + 0.0012 * feed_dev - 0.0016 * tol_dev - 0.0010 * reb_dev,
        )

        # Benzene purity — separation energy & feed composition
        purity_gain = (
            0.0040 * (xn["F_Reflux"] - 25.0) / 10.0
            + 0.0030 * (xn["F_Reboil"] - 1.2)
            + 0.0025 * (feed_zB - 0.60) / 0.05
            - 0.0040 * fouling_cond
            - 0.0030 * fouling_reb
        )
        xn["xB_sd"] = _clip("xB_sd", x["xB_sd"] + purity_gain)

        # Column differential pressure — vapour traffic & fouling
        xn["dP_col"] = _clip(
            "dP_col",
            x["dP_col"]
            + 0.012 * fouling_cond
            + 0.010 * feed_dev / 40.0
            + 0.006 * (xn["F_Reflux"] - 25.0) / 15.0
            - 0.004 * (xn["F_ToTol"] - 55.0) / 15.0,
        )

        # Overhead temperature — VLE estimate
        bz_reflux = np.clip(
            0.92 + 0.06 * (xn["xB_sd"] - 0.992) / 0.008 - 0.05 * fouling_cond,
            0.85, 0.998,
        )
        top_temp = self._overhead_T_from_VLE(float(bz_reflux), feed_fluid)
        fouling_bias = 12.0 * fouling_cond + 6.0 * fouling_reb
        xn["T_top"] = _clip("T_top", top_temp + fouling_bias)

        return xn

    # ---- Public API -------------------------------------------------------

    def step(self, u: Dict[str, float], scenario: Dict[str, float]) -> Dict[str, float]:
        return self.physics_step(self.state, u, scenario)

    def commit(self, x_next: Dict[str, float]) -> None:
        self.state = dict(x_next)

    def esd_safe_state(self) -> None:
        self.state["F_Reflux"] = _clip("F_Reflux", 20.0)
        self.state["F_Reboil"] = _clip("F_Reboil", 0.5)
        self.state["F_ToTol"] = _clip("F_ToTol", 45.0)
        self.state["xB_sd"] = max(self.state.get("xB_sd", 0.95) - 0.002, 0.90)
        self.state["dP_col"] = min(self.state.get("dP_col", 0.20), 0.25)
        self.state["T_top"] = _clip("T_top", self.state.get("T_top", 90.0) - 5.0)
