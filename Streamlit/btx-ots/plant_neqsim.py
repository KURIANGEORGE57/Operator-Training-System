"""Plant model powered by NeqSim thermo helpers.

This module contains :class:`PlantNeqSim`, a light-weight dynamic
representation of the benzene/toluene column used by the BTX OTS
prototype.  The model keeps the same public API as the legacy
:mod:`plant_stub` module while replacing the heuristic correlations with
helpers backed by `neqsim` to compute vapour-liquid equilibrium (VLE)
relationships.  The dynamics are intentionally simple (first order) to
remain inexpensive for Streamlit, yet the inclusion of the thermo helper
functions gives the controller and guard-rail logic a more realistic
response surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional
import logging
import warnings

import numpy as np

from plant_base import PlantBase

# Configure logging for NeqSim integration
logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency for richer physics
    from neqsim.thermo import fluid
    from neqsim.thermo.thermoTools import PHflash, TPflash

    _HAVE_NEQSIM = True
    logger.info("NeqSim thermo library loaded successfully")
except ImportError as e:
    # NeqSim not installed - expected in some environments
    fluid = None  # type: ignore[assignment]
    PHflash = None  # type: ignore[assignment]
    TPflash = None  # type: ignore[assignment]
    _HAVE_NEQSIM = False
    logger.info(
        "NeqSim not available (ImportError: %s). "
        "Using correlation-based fallback for thermodynamic calculations.",
        str(e),
    )
except Exception as e:
    # Unexpected error during import
    fluid = None  # type: ignore[assignment]
    PHflash = None  # type: ignore[assignment]
    TPflash = None  # type: ignore[assignment]
    _HAVE_NEQSIM = False
    logger.warning(
        "Unexpected error loading NeqSim (%s: %s). "
        "Using correlation-based fallback for thermodynamic calculations.",
        type(e).__name__,
        str(e),
    )


@dataclass
class _ColumnSpec:
    """Convenience structure holding the pseudo steady-state design data."""

    overhead_pressure_bar: float = 1.6
    condenser_duty_tau: float = 0.5
    reboiler_tau: float = 0.5
    inventory_tau: float = 0.25
    feed_temperature_c: float = 95.0
    feed_pressure_bar: float = 2.2


class PlantNeqSim(PlantBase):
    """First-order benzene/toluene column model using NeqSim for VLE.

    The class exposes the same small API as the historical ``Plant`` stub:

    ``state``
        Dictionary with the key KPIs tracked by the UI.  Every call to
        :meth:`step` returns a new dictionary while :meth:`commit` updates
        the internal copy that becomes the plant state for the next turn.

    ``step(u, scenario)``
        Evaluate the dynamics with the proposed set-points and scenario
        disturbances without mutating :attr:`state`.

    ``commit(x_next)``
        Accept the tentative state coming from :meth:`step`.

    ``esd_safe_state()``
        Apply an emergency shut-down profile that also acts as a reset for
        the controllers.

    The model purposefully avoids a full rigorous column solution – each
    manipulated variable is tracked by a first-order lag to mimic actuator
    dynamics, and the key quality variables depend on the thermo helper
    routines.  When the :mod:`neqsim` package is unavailable the code falls
    back to smooth correlations so that the Streamlit application can still
    run in documentation / demo environments.
    """

    def __init__(self) -> None:
        self.spec = _ColumnSpec()
        self.state: Dict[str, float] = {
            "xB_sd": 0.9950,   # benzene purity (side-draw)
            "dP_col": 0.08,    # bar
            "T_top": 84.5,     # °C
            "L_Drum": 0.65,    # 0..1
            "L_Bot":  0.56,    # 0..1
            "F_Reflux": 25.0,  # t/h (actual)
            "F_Reboil": 1.20,  # MW eq. (proxy)
            "F_ToTol":  55.0,  # t/h
        }
        # Cached fluid used to evaluate thermo properties for the current
        # scenario (makes the physics step cheaper).
        self._cached_feed: Optional[object] = None
        self._cached_feed_signature: Optional[tuple] = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _clip(name: str, value: float) -> float:
        bounds = {
            "xB_sd": (0.90, 0.9999),
            "dP_col": (0.02, 0.40),
            "T_top": (60.0, 110.0),
            "L_Drum": (0.0, 1.0),
            "L_Bot": (0.0, 1.0),
            "F_Reflux": (10.0, 45.0),
            "F_Reboil": (0.3, 3.5),
            "F_ToTol": (30.0, 90.0),
        }
        lo, hi = bounds[name]
        return float(np.clip(value, lo, hi))

    def _make_feed_fluid(self, flow_tph: float, zB: float) -> Optional[object]:
        """Construct or reuse a NeqSim fluid for the given feed conditions.

        Args:
            flow_tph: Feed flow rate (tonnes per hour)
            zB: Benzene mole fraction in feed (0-1)

        Returns:
            NeqSim fluid object if available, otherwise a dict with basic properties.
            Returns cached object if conditions match previous call.

        Note:
            Gracefully falls back to correlation-based dict if NeqSim fails.
        """
        signature = (round(flow_tph, 1), round(zB, 4))
        if self._cached_feed_signature == signature:
            return self._cached_feed

        if not _HAVE_NEQSIM:
            # NeqSim not available - use simple dict fallback
            self._cached_feed = {"zB": zB, "flow": flow_tph}
            self._cached_feed_signature = signature
            return self._cached_feed

        try:
            # Create NeqSim fluid with SRK equation of state
            feed = fluid("srk")  # type: ignore[operator]
            feed.addComponent("benzene", max(zB, 1e-5))
            feed.addComponent("toluene", max(1.0 - zB, 1e-5))
            feed.setMixingRule(2)
            feed.setTemperature(self.spec.feed_temperature_c + 273.15)
            feed.setPressure(self.spec.feed_pressure_bar)
            feed.setTotalFlowRate(max(flow_tph, 1e-3), "kg/hr")
            feed.init(1)

            logger.debug(
                "Created NeqSim feed fluid: %.1f t/h, zB=%.4f", flow_tph, zB
            )

        except (ValueError, AttributeError) as e:
            # NeqSim parameter error - log and fall back to correlation
            logger.warning(
                "NeqSim feed fluid creation failed (%s: %s). "
                "Using correlation fallback for flow=%.1f t/h, zB=%.4f",
                type(e).__name__,
                str(e),
                flow_tph,
                zB,
            )
            feed = {"zB": zB, "flow": flow_tph}

        except Exception as e:
            # Unexpected error - log and fall back
            logger.error(
                "Unexpected error creating NeqSim feed fluid (%s: %s). "
                "Using correlation fallback for flow=%.1f t/h, zB=%.4f",
                type(e).__name__,
                str(e),
                flow_tph,
                zB,
            )
            feed = {"zB": zB, "flow": flow_tph}

        self._cached_feed = feed
        self._cached_feed_signature = signature
        return feed

    def _overhead_T_from_VLE(self, liq_benzene: float, feed_obj: Optional[object]) -> float:
        """Return an overhead temperature estimate based on VLE.

        Args:
            liq_benzene: Benzene mole fraction in overhead liquid (0-1)
            feed_obj: NeqSim feed fluid object (or dict fallback)

        Returns:
            Overhead temperature in °C

        Note:
            Uses NeqSim TPflash if available, otherwise uses empirical correlation.
        """
        liq_benzene = float(np.clip(liq_benzene, 1e-4, 0.9999))

        if _HAVE_NEQSIM and feed_obj is not None and isinstance(feed_obj, dict) is False:
            try:
                # Create overhead vapor-liquid system and flash to equilibrium
                top = fluid("srk")  # type: ignore[operator]
                top.addComponent("benzene", liq_benzene)
                top.addComponent("toluene", 1.0 - liq_benzene)
                top.setMixingRule(2)
                top.setTemperature(350.0)  # initial guess (K)
                top.setPressure(self.spec.overhead_pressure_bar)
                top.init(1)
                TPflash(top)

                temp_c = float(top.getTemperature() - 273.15)
                logger.debug(
                    "NeqSim VLE calculation: xB=%.4f -> T=%.2f°C",
                    liq_benzene,
                    temp_c,
                )
                return temp_c

            except (ValueError, AttributeError) as e:
                # NeqSim calculation error - fall back to correlation
                logger.warning(
                    "NeqSim VLE calculation failed (%s: %s) for xB=%.4f. "
                    "Using correlation fallback.",
                    type(e).__name__,
                    str(e),
                    liq_benzene,
                )

            except Exception as e:
                # Unexpected error - log and fall back
                logger.error(
                    "Unexpected error in NeqSim VLE calculation (%s: %s) for xB=%.4f. "
                    "Using correlation fallback.",
                    type(e).__name__,
                    str(e),
                    liq_benzene,
                )

        # Fallback: smooth correlation anchored to typical dew points
        # This correlation approximates benzene-toluene VLE behavior
        base = 80.1  # benzene boiling point at ~1 atm (°C)
        tol_shift = 21.0  # toluene heavier -> hotter (toluene BP ~110°C)
        blend = base + tol_shift * (1.0 - liq_benzene) ** 0.85
        return self._clip("T_top", blend)

    # ------------------------------------------------------------------
    # Physics integration
    # ------------------------------------------------------------------
    def physics_step(self, x: Dict[str, float], u: Dict[str, float], sc: Dict[str, float]) -> Dict[str, float]:
        """Light-weight dynamic update for the benzene column state."""

        x_next = dict(x)

        feed_flow = float(sc.get("F_feed", 80.0))
        feed_zB = float(sc.get("zB_feed", 0.60))
        fouling_cond = float(sc.get("Fouling_Cond", 0.0))
        fouling_reb = float(sc.get("Fouling_Reb", 0.0))

        feed_fluid = self._make_feed_fluid(feed_flow, feed_zB)

        # Manipulated variable tracking (first-order lag)
        for key, tau in (
            ("F_Reflux", self.spec.condenser_duty_tau),
            ("F_Reboil", self.spec.reboiler_tau),
            ("F_ToTol", self.spec.inventory_tau),
        ):
            sp_key = {
                "F_Reflux": "SP_F_Reflux",
                "F_Reboil": "SP_F_Reboil",
                "F_ToTol": "SP_F_ToTol",
            }[key]
            delta = (u[sp_key] - x[key])
            x_next[key] = self._clip(key, x[key] + (1.0 - np.exp(-1.0 / tau)) * delta)

        # Simple level dynamics – mass balance influenced by feed & draws
        reflux_dev = x_next["F_Reflux"] - 25.0
        feed_dev = feed_flow - 80.0
        toluene_draw_dev = x_next["F_ToTol"] - 55.0
        reboil_dev = x_next["F_Reboil"] - 1.2

        x_next["L_Drum"] = self._clip(
            "L_Drum",
            x["L_Drum"]
            + 0.0025 * reflux_dev
            - 0.0015 * toluene_draw_dev
            + 0.0010 * feed_dev,
        )
        x_next["L_Bot"] = self._clip(
            "L_Bot",
            x["L_Bot"]
            + 0.0012 * feed_dev
            - 0.0016 * toluene_draw_dev
            - 0.0010 * reboil_dev,
        )

        # Benzene purity (side draw) responds to separation energy & feed
        quality_base = x["xB_sd"]
        purity_gain = (
            0.0040 * (x_next["F_Reflux"] - 25.0) / 10.0
            + 0.0030 * (x_next["F_Reboil"] - 1.2)
            + 0.0025 * (feed_zB - 0.60) / 0.05
            - 0.0040 * fouling_cond
            - 0.0030 * fouling_reb
        )
        x_next["xB_sd"] = self._clip("xB_sd", quality_base + purity_gain)

        # Column differential pressure increases with vapour traffic & fouling
        x_next["dP_col"] = self._clip(
            "dP_col",
            x["dP_col"]
            + 0.012 * fouling_cond
            + 0.010 * feed_dev / 40.0
            + 0.006 * (x_next["F_Reflux"] - 25.0) / 15.0
            - 0.004 * (x_next["F_ToTol"] - 55.0) / 15.0,
        )

        # Overhead temperature from VLE estimate
        benzene_reflux = np.clip(0.92 + 0.06 * (x_next["xB_sd"] - 0.992) / 0.008 - 0.05 * fouling_cond, 0.85, 0.998)
        top_temp = self._overhead_T_from_VLE(float(benzene_reflux), feed_fluid)
        fouling_temp_bias = 12.0 * fouling_cond + 6.0 * fouling_reb
        x_next["T_top"] = self._clip("T_top", top_temp + fouling_temp_bias)

        return x_next

    # ------------------------------------------------------------------
    # Public API used by the Streamlit UI
    # ------------------------------------------------------------------
    def step(self, u: Dict[str, float], scenario: Dict[str, float]) -> Dict[str, float]:
        """Compute tentative next state (no commit)."""

        return self.physics_step(self.state, u, scenario)

    def commit(self, x_next: Dict[str, float]) -> None:
        self.state = dict(x_next)

    def esd_safe_state(self) -> None:
        """Move the plant towards a conservative safe configuration."""

        safe = {
            "F_Reflux": 20.0,
            "F_Reboil": 0.5,
            "F_ToTol": 45.0,
        }
        self.state.update({k: self._clip(k, v) for k, v in safe.items()})
        self.state["xB_sd"] = max(self.state.get("xB_sd", 0.95) - 0.002, 0.90)
        self.state["dP_col"] = min(self.state.get("dP_col", 0.20), 0.25)
        self.state["T_top"] = self._clip("T_top", self.state.get("T_top", 90.0) - 5.0)
