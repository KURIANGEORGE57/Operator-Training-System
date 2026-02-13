"""Three-tier safety system for the benzene column.

Tier 1 - Alarms:      Early warnings for operator awareness.
Tier 2 - Interlocks:  Automatic protective actions to prevent hazards.
Tier 3 - ESD:         Emergency shutdown for critical conditions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from src.models.constants import LIMITS
from src.models.plant_state import PlantState


@dataclass
class SafetyResult:
    """Outcome of a safety evaluation."""

    alarms: List[str] = field(default_factory=list)
    interlock_active: bool = False
    interlock_reason: str = ""
    adjusted_inputs: Dict[str, float] = field(default_factory=dict)
    esd_triggered: bool = False
    esd_reason: str = ""

    @property
    def is_clear(self) -> bool:
        return not self.alarms and not self.interlock_active and not self.esd_triggered


def evaluate_safety(
    x_next: PlantState, u_applied: Dict[str, float]
) -> SafetyResult:
    """Evaluate the three-tier safety system against a tentative plant state.

    Args:
        x_next: Tentative next plant state (from plant.step()).
        u_applied: Control inputs that produced x_next.

    Returns:
        SafetyResult with alarms, interlock adjustments, or ESD flag.
    """
    result = SafetyResult()

    # --- Tier 3: Emergency Shutdown (checked first - highest priority) ---
    if x_next.dP_col > LIMITS.dP_esd:
        result.esd_triggered = True
        result.esd_reason = f"Critical column dP: {x_next.dP_col:.3f} bar > {LIMITS.dP_esd} bar"
        return result

    if x_next.T_top > LIMITS.T_top_esd:
        result.esd_triggered = True
        result.esd_reason = f"Critical overhead T: {x_next.T_top:.1f} C > {LIMITS.T_top_esd} C"
        return result

    if x_next.L_Drum < LIMITS.L_drum_esd:
        result.esd_triggered = True
        result.esd_reason = f"Critical drum level: {x_next.L_Drum:.3f} < {LIMITS.L_drum_esd}"
        return result

    # --- Tier 2: Interlocks ---
    if x_next.dP_col > LIMITS.dP_interlock:
        result.interlock_active = True
        result.interlock_reason = (
            f"Flooding interlock: dP {x_next.dP_col:.3f} bar > {LIMITS.dP_interlock} bar"
        )
        adjusted = dict(u_applied)
        adjusted["SP_F_Reboil"] = max(u_applied["SP_F_Reboil"] - 0.2, 0.3)
        adjusted["SP_F_Reflux"] = min(u_applied["SP_F_Reflux"] + 2.0, 45.0)
        result.adjusted_inputs = adjusted

    # --- Tier 1: Alarms ---
    if x_next.dP_col > LIMITS.dP_alarm:
        result.alarms.append(f"HIGH dP: {x_next.dP_col:.3f} bar")

    if x_next.T_top > LIMITS.T_top_alarm:
        result.alarms.append(f"HIGH T_top: {x_next.T_top:.1f} C")

    if x_next.xB_sd < LIMITS.xB_spec:
        result.alarms.append(f"OFF-SPEC xB: {x_next.xB_sd:.4f}")

    if x_next.L_Drum < LIMITS.L_drum_alarm:
        result.alarms.append(f"LOW drum level: {x_next.L_Drum:.3f}")

    if x_next.L_Bot < LIMITS.L_bot_alarm:
        result.alarms.append(f"LOW bottoms level: {x_next.L_Bot:.3f}")

    return result
