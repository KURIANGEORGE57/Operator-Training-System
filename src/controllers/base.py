"""Abstract controller interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict

from src.models.plant_state import PlantState


class Controller(ABC):
    """Base class for automated controllers."""

    @abstractmethod
    def decide(
        self,
        state: PlantState,
        scenario: Dict[str, float],
    ) -> Dict[str, float]:
        """Compute control action given current state and scenario.

        Returns:
            Dict with keys SP_F_Reflux, SP_F_Reboil, SP_F_ToTol.
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable controller name."""
