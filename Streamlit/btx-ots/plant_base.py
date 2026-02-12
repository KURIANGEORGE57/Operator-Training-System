"""Abstract base class for all plant models in the BTX OTS.

Defines the two-phase commit interface: step() computes a tentative next
state, commit() accepts it.  This lets safety logic inspect the proposed
state before it becomes real.
"""

from abc import ABC, abstractmethod
from typing import Dict


class PlantBase(ABC):
    """Interface contract for benzene-toluene column models.

    Required state keys: xB_sd, dP_col, T_top, L_Drum, L_Bot,
    F_Reflux, F_Reboil, F_ToTol.
    """

    def __init__(self) -> None:
        self._state: Dict[str, float] = {}

    @property
    def state(self) -> Dict[str, float]:
        return self._state

    @state.setter
    def state(self, new_state: Dict[str, float]) -> None:
        self._state = new_state

    @abstractmethod
    def step(self, u: Dict[str, float], scenario: Dict[str, float]) -> Dict[str, float]:
        """Compute tentative next state WITHOUT modifying internal state.

        Args:
            u: Setpoints — SP_F_Reflux, SP_F_Reboil, SP_F_ToTol.
            scenario: Disturbances — F_feed, zB_feed, Fouling_Cond, Fouling_Reb.

        Returns:
            New state dict (internal state unchanged).
        """

    @abstractmethod
    def commit(self, x_next: Dict[str, float]) -> None:
        """Accept a tentative state from step() as the new plant state."""

    @abstractmethod
    def esd_safe_state(self) -> None:
        """Immediately move the plant to a conservative safe configuration.

        Called when the safety system triggers an emergency shutdown.
        Modifies internal state directly (no two-phase commit).
        """

    def physics_step(
        self, x: Dict[str, float], u: Dict[str, float], sc: Dict[str, float]
    ) -> Dict[str, float]:
        """Optional helper for physics calculations."""
        raise NotImplementedError(
            "physics_step() is optional. Override step() or provide physics_step()."
        )
