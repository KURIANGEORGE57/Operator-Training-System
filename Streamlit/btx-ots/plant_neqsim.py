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

import numpy as np

from plant_constants import (
    COLUMN_SPEC_DEFAULTS,
    INITIAL_STATE,
    VARIABLE_BOUNDS,
    MIN_COMPOSITION,
    MIN_FLOW_RATE,
    KELVIN_OFFSET,
    INITIAL_TEMP_GUESS_K,
    VLE_FALLBACK,
    SIGNATURE_PRECISION,
    LEVEL_DYNAMICS,
    PURITY_DYNAMICS,
    PRESSURE_DROP_DYNAMICS,
    OVERHEAD_TEMP,
    ESD_SAFE_STATE,
    DEFAULT_SCENARIO,
)

try:  # pragma: no cover - optional dependency for richer physics
    from neqsim.thermo import fluid
    from neqsim.thermo.thermoTools import PHflash, TPflash

    _HAVE_NEQSIM = True
except Exception:  # pragma: no cover - best effort guardrail
    fluid = None  # type: ignore[assignment]
    PHflash = None  # type: ignore[assignment]
    TPflash = None  # type: ignore[assignment]
    _HAVE_NEQSIM = False


@dataclass
class _ColumnSpec:
    """Convenience structure holding the pseudo steady-state design data."""

    overhead_pressure_bar: float = COLUMN_SPEC_DEFAULTS["overhead_pressure_bar"]
    condenser_duty_tau: float = COLUMN_SPEC_DEFAULTS["condenser_duty_tau"]
    reboiler_tau: float = COLUMN_SPEC_DEFAULTS["reboiler_tau"]
    inventory_tau: float = COLUMN_SPEC_DEFAULTS["inventory_tau"]
    feed_temperature_c: float = COLUMN_SPEC_DEFAULTS["feed_temperature_c"]
    feed_pressure_bar: float = COLUMN_SPEC_DEFAULTS["feed_pressure_bar"]


class PlantNeqSim:
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
        self.state: Dict[str, float] = INITIAL_STATE.copy()
        # Cached fluid used to evaluate thermo properties for the current
        # scenario (makes the physics step cheaper).
        self._cached_feed: Optional[object] = None
        self._cached_feed_signature: Optional[tuple] = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _clip(name: str, value: float) -> float:
        """Clip variable to its valid bounds."""
        lo, hi = VARIABLE_BOUNDS[name]
        return float(np.clip(value, lo, hi))

    def _make_feed_fluid(self, flow_tph: float, zB: float) -> Optional[object]:
        """Construct or reuse a NeqSim fluid for the given feed conditions."""

        signature = (
            round(flow_tph, SIGNATURE_PRECISION["flow_tph"]),
            round(zB, SIGNATURE_PRECISION["zB"])
        )
        if self._cached_feed_signature == signature:
            return self._cached_feed

        if not _HAVE_NEQSIM:
            self._cached_feed = {"zB": zB, "flow": flow_tph}
            self._cached_feed_signature = signature
            return self._cached_feed

        try:
            feed = fluid("srk")  # type: ignore[operator]
            feed.addComponent("benzene", max(zB, MIN_COMPOSITION))
            feed.addComponent("toluene", max(1.0 - zB, MIN_COMPOSITION))
            feed.setMixingRule(2)
            feed.setTemperature(self.spec.feed_temperature_c + KELVIN_OFFSET)
            feed.setPressure(self.spec.feed_pressure_bar)
            feed.setTotalFlowRate(max(flow_tph, MIN_FLOW_RATE), "kg/hr")
            feed.init(1)
        except Exception:
            # Degrade gracefully – behave like the pure dict fallback.
            feed = {"zB": zB, "flow": flow_tph}

        self._cached_feed = feed
        self._cached_feed_signature = signature
        return feed

    def _overhead_T_from_VLE(self, liq_benzene: float, feed_obj: Optional[object]) -> float:
        """Return an overhead temperature estimate based on VLE."""

        liq_benzene = float(np.clip(
            liq_benzene,
            OVERHEAD_TEMP["benzene_clip_min"],
            OVERHEAD_TEMP["benzene_clip_max"]
        ))

        if _HAVE_NEQSIM and feed_obj is not None:
            try:
                top = fluid("srk")  # type: ignore[operator]
                top.addComponent("benzene", liq_benzene)
                top.addComponent("toluene", 1.0 - liq_benzene)
                top.setMixingRule(2)
                top.setTemperature(INITIAL_TEMP_GUESS_K)
                top.setPressure(self.spec.overhead_pressure_bar)
                top.init(1)
                TPflash(top)
                return float(top.getTemperature() - KELVIN_OFFSET)
            except Exception:
                pass

        # Fallback: smooth correlation anchored to typical dew points
        base = VLE_FALLBACK["benzene_bp_c"]
        tol_shift = VLE_FALLBACK["toluene_shift_c"]
        blend = base + tol_shift * (1.0 - liq_benzene) ** VLE_FALLBACK["toluene_exponent"]
        return self._clip("T_top", blend)

    # ------------------------------------------------------------------
    # Physics integration
    # ------------------------------------------------------------------
    def physics_step(self, x: Dict[str, float], u: Dict[str, float], sc: Dict[str, float]) -> Dict[str, float]:
        """Light-weight dynamic update for the benzene column state."""

        x_next = dict(x)

        feed_flow = float(sc.get("F_feed", DEFAULT_SCENARIO["F_feed"]))
        feed_zB = float(sc.get("zB_feed", DEFAULT_SCENARIO["zB_feed"]))
        fouling_cond = float(sc.get("Fouling_Cond", DEFAULT_SCENARIO["Fouling_Cond"]))
        fouling_reb = float(sc.get("Fouling_Reb", DEFAULT_SCENARIO["Fouling_Reb"]))

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
        reflux_dev = x_next["F_Reflux"] - PURITY_DYNAMICS["reflux_nominal"]
        feed_dev = feed_flow - PRESSURE_DROP_DYNAMICS["feed_nominal"]
        toluene_draw_dev = x_next["F_ToTol"] - PRESSURE_DROP_DYNAMICS["totol_nominal"]
        reboil_dev = x_next["F_Reboil"] - PURITY_DYNAMICS["reboil_nominal"]

        x_next["L_Drum"] = self._clip(
            "L_Drum",
            x["L_Drum"]
            + LEVEL_DYNAMICS["drum_reflux_coeff"] * reflux_dev
            + LEVEL_DYNAMICS["drum_totol_coeff"] * toluene_draw_dev
            + LEVEL_DYNAMICS["drum_feed_coeff"] * feed_dev,
        )
        x_next["L_Bot"] = self._clip(
            "L_Bot",
            x["L_Bot"]
            + LEVEL_DYNAMICS["bot_feed_coeff"] * feed_dev
            + LEVEL_DYNAMICS["bot_totol_coeff"] * toluene_draw_dev
            + LEVEL_DYNAMICS["bot_reboil_coeff"] * reboil_dev,
        )

        # Benzene purity (side draw) responds to separation energy & feed
        quality_base = x["xB_sd"]
        purity_gain = (
            PURITY_DYNAMICS["reflux_gain"] * (x_next["F_Reflux"] - PURITY_DYNAMICS["reflux_nominal"]) / PURITY_DYNAMICS["reflux_scale"]
            + PURITY_DYNAMICS["reboil_gain"] * (x_next["F_Reboil"] - PURITY_DYNAMICS["reboil_nominal"])
            + PURITY_DYNAMICS["feed_gain"] * (feed_zB - PURITY_DYNAMICS["feed_nominal"]) / PURITY_DYNAMICS["feed_scale"]
            + PURITY_DYNAMICS["cond_fouling_penalty"] * fouling_cond
            + PURITY_DYNAMICS["reb_fouling_penalty"] * fouling_reb
        )
        x_next["xB_sd"] = self._clip("xB_sd", quality_base + purity_gain)

        # Column differential pressure increases with vapour traffic & fouling
        x_next["dP_col"] = self._clip(
            "dP_col",
            x["dP_col"]
            + PRESSURE_DROP_DYNAMICS["cond_fouling_coeff"] * fouling_cond
            + PRESSURE_DROP_DYNAMICS["feed_dev_coeff"] * feed_dev / PRESSURE_DROP_DYNAMICS["feed_scale"]
            + PRESSURE_DROP_DYNAMICS["reflux_coeff"] * (x_next["F_Reflux"] - PRESSURE_DROP_DYNAMICS["reflux_nominal"]) / PRESSURE_DROP_DYNAMICS["reflux_scale"]
            + PRESSURE_DROP_DYNAMICS["totol_coeff"] * (x_next["F_ToTol"] - PRESSURE_DROP_DYNAMICS["totol_nominal"]) / PRESSURE_DROP_DYNAMICS["totol_scale"],
        )

        # Overhead temperature from VLE estimate
        benzene_reflux = np.clip(
            OVERHEAD_TEMP["benzene_base_purity"]
            + OVERHEAD_TEMP["benzene_purity_gain"] * (x_next["xB_sd"] - OVERHEAD_TEMP["purity_nominal"]) / OVERHEAD_TEMP["purity_scale"]
            + OVERHEAD_TEMP["fouling_penalty"] * fouling_cond,
            OVERHEAD_TEMP["min_benzene_reflux"],
            OVERHEAD_TEMP["max_benzene_reflux"]
        )
        top_temp = self._overhead_T_from_VLE(float(benzene_reflux), feed_fluid)
        fouling_temp_bias = (
            OVERHEAD_TEMP["cond_fouling_temp_bias"] * fouling_cond
            + OVERHEAD_TEMP["reb_fouling_temp_bias"] * fouling_reb
        )
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
            "F_Reflux": ESD_SAFE_STATE["F_Reflux"],
            "F_Reboil": ESD_SAFE_STATE["F_Reboil"],
            "F_ToTol": ESD_SAFE_STATE["F_ToTol"],
        }
        self.state.update({k: self._clip(k, v) for k, v in safe.items()})
        self.state["xB_sd"] = max(
            self.state.get("xB_sd", INITIAL_STATE["xB_sd"]) - ESD_SAFE_STATE["xB_sd_decrease"],
            ESD_SAFE_STATE["xB_sd_min"]
        )
        self.state["dP_col"] = min(
            self.state.get("dP_col", INITIAL_STATE["dP_col"]),
            ESD_SAFE_STATE["dP_col_max"]
        )
        self.state["T_top"] = self._clip(
            "T_top",
            self.state.get("T_top", INITIAL_STATE["T_top"]) - ESD_SAFE_STATE["T_top_decrease"]
        )
