"""Heat exchanger plant model for Operator Training System.

This module contains a dynamic shell-and-tube heat exchanger model with:
- Counter-flow configuration
- Hot side (process fluid) and cold side (cooling water)
- Fouling effects on both sides
- Tube leakage scenarios
- Flow upsets and pump trips
- Realistic thermal dynamics
"""

from __future__ import annotations

import sys
import os
from dataclasses import dataclass
from typing import Dict, Optional
import logging

import numpy as np

# Add parent directory to path to import PlantBase
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'btx-ots'))
from plant_base import PlantBase

logger = logging.getLogger(__name__)


@dataclass
class HeatExchangerSpec:
    """Design specifications for shell-and-tube heat exchanger."""

    # Design conditions
    design_UA: float = 250.0  # Overall heat transfer coefficient × Area (kW/K)
    hot_side_tau: float = 2.0  # Hot side thermal time constant (minutes)
    cold_side_tau: float = 1.5  # Cold side thermal time constant (minutes)
    flow_tau: float = 0.5  # Flow response time constant (minutes)

    # Physical properties (simplified)
    cp_hot: float = 4.2  # Hot fluid heat capacity (kJ/kg·K)
    cp_cold: float = 4.18  # Cold fluid heat capacity (kJ/kg·K)

    # Safety limits
    max_hot_temp: float = 150.0  # Maximum hot outlet temperature (°C)
    max_cold_temp: float = 60.0  # Maximum cold outlet temperature (°C)
    max_hot_dp: float = 2.5  # Maximum hot side pressure drop (bar)
    max_cold_dp: float = 1.5  # Maximum cold side pressure drop (bar)
    min_flow_hot: float = 10.0  # Minimum hot side flow (kg/s)
    min_flow_cold: float = 15.0  # Minimum cold side flow (kg/s)


class PlantHeatExchanger(PlantBase):
    """Dynamic heat exchanger model with safety systems.

    This model simulates a counter-flow shell-and-tube heat exchanger
    with realistic dynamics, fouling, and failure modes.

    State Variables:
        T_hot_in: Hot side inlet temperature (°C)
        T_hot_out: Hot side outlet temperature (°C)
        T_cold_in: Cold side inlet temperature (°C)
        T_cold_out: Cold side outlet temperature (°C)
        F_hot: Hot side flow rate (kg/s)
        F_cold: Cold side flow rate (kg/s)
        dP_hot: Hot side pressure drop (bar)
        dP_cold: Cold side pressure drop (bar)
        Q_duty: Heat duty (kW)
        fouling_hot: Hot side fouling factor (0-1, 0=clean)
        fouling_cold: Cold side fouling factor (0-1, 0=clean)
        tube_leak: Tube leakage severity (0-1, 0=no leak)

    Control Inputs (setpoints):
        SP_F_hot: Hot side flow setpoint (kg/s)
        SP_F_cold: Cold side flow setpoint (kg/s)

    Scenario Parameters:
        T_hot_in_feed: Hot fluid feed temperature (°C)
        T_cold_in_feed: Cold water inlet temperature (°C)
        fouling_hot_rate: Hot side fouling rate (%/turn)
        fouling_cold_rate: Cold side fouling rate (%/turn)
        tube_leak_severity: Tube leak severity (0-1)
        hot_pump_trip: Hot pump trip flag (0=ok, 1=tripped)
        cold_pump_trip: Cold pump trip flag (0=ok, 1=tripped)
    """

    def __init__(self) -> None:
        """Initialize heat exchanger with nominal operating conditions."""
        super().__init__()
        self.spec = HeatExchangerSpec()

        # Initialize at nominal steady state
        self._state = {
            # Temperatures
            "T_hot_in": 120.0,
            "T_hot_out": 60.0,
            "T_cold_in": 25.0,
            "T_cold_out": 45.0,

            # Flows
            "F_hot": 30.0,  # kg/s
            "F_cold": 50.0,  # kg/s

            # Pressure drops
            "dP_hot": 0.8,  # bar
            "dP_cold": 0.4,  # bar

            # Heat duty
            "Q_duty": 7560.0,  # kW

            # Fouling and failures
            "fouling_hot": 0.0,  # 0-1 scale
            "fouling_cold": 0.0,  # 0-1 scale
            "tube_leak": 0.0,  # 0-1 scale
        }

        logger.info("Heat exchanger plant model initialized")

    @staticmethod
    def _clip(name: str, value: float) -> float:
        """Clip state variables to physical bounds."""
        bounds = {
            "T_hot_in": (20.0, 200.0),
            "T_hot_out": (20.0, 200.0),
            "T_cold_in": (10.0, 80.0),
            "T_cold_out": (10.0, 80.0),
            "F_hot": (0.0, 100.0),
            "F_cold": (0.0, 150.0),
            "dP_hot": (0.0, 5.0),
            "dP_cold": (0.0, 3.0),
            "Q_duty": (0.0, 20000.0),
            "fouling_hot": (0.0, 0.95),
            "fouling_cold": (0.0, 0.95),
            "tube_leak": (0.0, 1.0),
        }
        lo, hi = bounds[name]
        return float(np.clip(value, lo, hi))

    def _calculate_UA(self, fouling_hot: float, fouling_cold: float) -> float:
        """Calculate effective UA with fouling degradation.

        Args:
            fouling_hot: Hot side fouling (0-1)
            fouling_cold: Cold side fouling (0-1)

        Returns:
            Effective UA value (kW/K)
        """
        # Fouling reduces heat transfer coefficient
        # UA_fouled = UA_clean / (1 + fouling_resistance)
        fouling_factor = 1.0 - 0.7 * fouling_hot - 0.5 * fouling_cold
        fouling_factor = max(fouling_factor, 0.1)  # Never go below 10% effectiveness

        return self.spec.design_UA * fouling_factor

    def _calculate_heat_duty(
        self, T_hot_in: float, T_hot_out: float, T_cold_in: float,
        T_cold_out: float, F_hot: float, F_cold: float, UA: float
    ) -> float:
        """Calculate actual heat duty using LMTD method.

        Args:
            T_hot_in, T_hot_out: Hot side temperatures (°C)
            T_cold_in, T_cold_out: Cold side temperatures (°C)
            F_hot, F_cold: Flow rates (kg/s)
            UA: Overall heat transfer coefficient (kW/K)

        Returns:
            Heat duty (kW)
        """
        # Counter-flow LMTD
        dT1 = T_hot_in - T_cold_out  # Hot in - Cold out
        dT2 = T_hot_out - T_cold_in  # Hot out - Cold in

        if dT1 <= 0 or dT2 <= 0:
            # Temperature cross - no heat transfer
            return 0.0

        if abs(dT1 - dT2) < 0.1:
            LMTD = dT1
        else:
            LMTD = (dT1 - dT2) / np.log(dT1 / dT2)

        # Q = UA × LMTD
        Q_lmtd = UA * LMTD

        # Also check energy balance
        Q_hot = F_hot * self.spec.cp_hot * (T_hot_in - T_hot_out)
        Q_cold = F_cold * self.spec.cp_cold * (T_cold_out - T_cold_in)

        # Use LMTD method but bound by energy balance
        return min(Q_lmtd, max(Q_hot, Q_cold))

    def physics_step(
        self, x: Dict[str, float], u: Dict[str, float], sc: Dict[str, float]
    ) -> Dict[str, float]:
        """Simulate one time step of heat exchanger dynamics.

        Args:
            x: Current state
            u: Control inputs (setpoints)
            sc: Scenario parameters (disturbances)

        Returns:
            Next state
        """
        x_next = dict(x)

        # Extract scenario parameters
        T_hot_in_feed = float(sc.get("T_hot_in_feed", 120.0))
        T_cold_in_feed = float(sc.get("T_cold_in_feed", 25.0))
        fouling_hot_rate = float(sc.get("fouling_hot_rate", 0.0)) / 100.0  # Convert % to fraction
        fouling_cold_rate = float(sc.get("fouling_cold_rate", 0.0)) / 100.0
        tube_leak_severity = float(sc.get("tube_leak_severity", 0.0))
        hot_pump_trip = bool(sc.get("hot_pump_trip", 0))
        cold_pump_trip = bool(sc.get("cold_pump_trip", 0))

        # Flow dynamics with first-order lag
        SP_F_hot = u.get("SP_F_hot", 30.0)
        SP_F_cold = u.get("SP_F_cold", 50.0)

        # Pump trips force flow to zero
        if hot_pump_trip:
            SP_F_hot = 0.0
        if cold_pump_trip:
            SP_F_cold = 0.0

        alpha_flow = 1.0 - np.exp(-1.0 / self.spec.flow_tau)
        x_next["F_hot"] = self._clip(
            "F_hot",
            x["F_hot"] + alpha_flow * (SP_F_hot - x["F_hot"])
        )
        x_next["F_cold"] = self._clip(
            "F_cold",
            x["F_cold"] + alpha_flow * (SP_F_cold - x["F_cold"])
        )

        # Fouling accumulation (slow drift)
        x_next["fouling_hot"] = self._clip(
            "fouling_hot",
            x["fouling_hot"] + fouling_hot_rate
        )
        x_next["fouling_cold"] = self._clip(
            "fouling_cold",
            x["fouling_cold"] + fouling_cold_rate
        )

        # Tube leak (instantaneous)
        x_next["tube_leak"] = self._clip("tube_leak", tube_leak_severity)

        # Calculate effective UA with fouling
        UA = self._calculate_UA(x_next["fouling_hot"], x_next["fouling_cold"])

        # Inlet temperatures (fast response to feed changes)
        x_next["T_hot_in"] = self._clip("T_hot_in", T_hot_in_feed)
        x_next["T_cold_in"] = self._clip("T_cold_in", T_cold_in_feed)

        # Tube leak causes mixing (hot fluid leaks into cold side)
        if x_next["tube_leak"] > 0.01:
            leak_fraction = x_next["tube_leak"] * 0.1  # Up to 10% leakage
            T_cold_contaminated = (
                T_cold_in_feed * (1 - leak_fraction) +
                x["T_hot_in"] * leak_fraction
            )
            x_next["T_cold_in"] = self._clip("T_cold_in", T_cold_contaminated)

        # Heat transfer dynamics
        # Simplified: outlet temperatures move toward energy balance

        # Target outlet temperatures from energy balance
        if x_next["F_hot"] > 1.0 and x_next["F_cold"] > 1.0:
            # Effectiveness-NTU method approximation
            NTU = UA / (min(
                x_next["F_hot"] * self.spec.cp_hot,
                x_next["F_cold"] * self.spec.cp_cold
            ))
            C_ratio = min(
                x_next["F_hot"] * self.spec.cp_hot,
                x_next["F_cold"] * self.spec.cp_cold
            ) / max(
                x_next["F_hot"] * self.spec.cp_hot,
                x_next["F_cold"] * self.spec.cp_cold
            )

            # Counter-flow effectiveness
            if abs(C_ratio - 1.0) < 0.01:
                effectiveness = NTU / (1.0 + NTU)
            else:
                effectiveness = (1.0 - np.exp(-NTU * (1.0 - C_ratio))) / (
                    1.0 - C_ratio * np.exp(-NTU * (1.0 - C_ratio))
                )
            effectiveness = min(effectiveness, 0.95)  # Practical limit

            Q_max = min(
                x_next["F_hot"] * self.spec.cp_hot,
                x_next["F_cold"] * self.spec.cp_cold
            ) * (x_next["T_hot_in"] - x_next["T_cold_in"])

            Q_actual = effectiveness * Q_max

            # Target outlet temperatures
            T_hot_out_target = x_next["T_hot_in"] - Q_actual / (
                x_next["F_hot"] * self.spec.cp_hot + 1e-6
            )
            T_cold_out_target = x_next["T_cold_in"] + Q_actual / (
                x_next["F_cold"] * self.spec.cp_cold + 1e-6
            )
        else:
            # No flow - temperatures drift toward ambient
            T_hot_out_target = 0.5 * (x["T_hot_out"] + x_next["T_cold_in"])
            T_cold_out_target = x_next["T_cold_in"]
            Q_actual = 0.0

        # First-order lag to target temperatures
        alpha_hot = 1.0 - np.exp(-1.0 / self.spec.hot_side_tau)
        alpha_cold = 1.0 - np.exp(-1.0 / self.spec.cold_side_tau)

        x_next["T_hot_out"] = self._clip(
            "T_hot_out",
            x["T_hot_out"] + alpha_hot * (T_hot_out_target - x["T_hot_out"])
        )
        x_next["T_cold_out"] = self._clip(
            "T_cold_out",
            x["T_cold_out"] + alpha_cold * (T_cold_out_target - x["T_cold_out"])
        )

        # Heat duty
        x_next["Q_duty"] = self._clip("Q_duty", Q_actual)

        # Pressure drop increases with flow and fouling
        # ΔP ∝ flow² × (1 + fouling_factor)
        flow_factor_hot = (x_next["F_hot"] / 30.0) ** 1.8  # Slightly non-linear
        fouling_factor_hot = 1.0 + 2.0 * x_next["fouling_hot"]
        x_next["dP_hot"] = self._clip(
            "dP_hot",
            0.8 * flow_factor_hot * fouling_factor_hot
        )

        flow_factor_cold = (x_next["F_cold"] / 50.0) ** 1.8
        fouling_factor_cold = 1.0 + 1.5 * x_next["fouling_cold"]
        x_next["dP_cold"] = self._clip(
            "dP_cold",
            0.4 * flow_factor_cold * fouling_factor_cold
        )

        return x_next

    def step(self, u: Dict[str, float], scenario: Dict[str, float]) -> Dict[str, float]:
        """Compute tentative next state without modifying internal state.

        Args:
            u: Control inputs (SP_F_hot, SP_F_cold)
            scenario: Scenario parameters (temperatures, fouling, failures)

        Returns:
            Next state dictionary
        """
        return self.physics_step(self._state, u, scenario)

    def commit(self, x_next: Dict[str, float]) -> None:
        """Accept and commit the next state.

        Args:
            x_next: State to commit
        """
        self._state = dict(x_next)

    def esd_safe_state(self) -> None:
        """Emergency shutdown: reduce flows and heat duty."""
        logger.warning("ESD triggered - moving to safe state")

        # Reduce flows to minimum safe values
        self._state["F_hot"] = self._clip("F_hot", 10.0)
        self._state["F_cold"] = self._clip("F_cold", 20.0)

        # Temperatures will naturally decrease with reduced flows
        self._state["T_hot_out"] = min(self._state["T_hot_out"], 80.0)
        self._state["T_cold_out"] = min(self._state["T_cold_out"], 50.0)

        # Pressure drops reduce with lower flows
        self._state["dP_hot"] = min(self._state["dP_hot"], 0.5)
        self._state["dP_cold"] = min(self._state["dP_cold"], 0.3)
