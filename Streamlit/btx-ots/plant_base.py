"""Base class for plant models in the Operator Training System.

This module defines the abstract interface that all plant models must
implement. It ensures consistency across different plant implementations
(e.g., PlantNeqSim, Plant stub) and provides a clear contract for
integration with controllers, safety systems, and the UI.
"""

from abc import ABC, abstractmethod
from typing import Dict


class PlantBase(ABC):
    """Abstract base class for plant models.

    This class defines the minimum interface required for a plant model
    to integrate with the OTS framework. All concrete plant implementations
    should inherit from this base class and implement the required methods.

    The plant model follows a two-phase commit pattern:
    1. `step()` computes a tentative next state without modifying internal state
    2. `commit()` accepts the tentative state and updates internal state

    This pattern allows safety systems and controllers to evaluate proposed
    actions before committing them, enabling rollback if safety violations occur.

    Attributes:
        state: Current plant state as a dictionary of key-value pairs.
               Must include at minimum the process variables monitored by
               the safety system and displayed in the UI.

    Required State Variables:
        - xB_sd: Benzene purity in side-draw (mol fraction, 0-1)
        - dP_col: Column differential pressure (bar)
        - T_top: Overhead temperature (°C)
        - L_Drum: Reflux drum level (fraction, 0-1)
        - L_Bot: Bottoms level (fraction, 0-1)
        - F_Reflux: Reflux flow rate (t/h)
        - F_Reboil: Reboiler duty (MW equivalent)
        - F_ToTol: Toluene transfer flow rate (t/h)
    """

    def __init__(self) -> None:
        """Initialize the plant model with default state.

        Concrete implementations should call super().__init__() and then
        initialize their state dictionary with appropriate default values.
        """
        self._state: Dict[str, float] = {}

    @property
    def state(self) -> Dict[str, float]:
        """Get the current plant state.

        Returns:
            Dictionary containing current values of all process variables.
        """
        return self._state

    @state.setter
    def state(self, new_state: Dict[str, float]) -> None:
        """Set the plant state.

        Args:
            new_state: Dictionary containing new values for process variables.
        """
        self._state = new_state

    @abstractmethod
    def step(self, u: Dict[str, float], scenario: Dict[str, float]) -> Dict[str, float]:
        """Compute tentative next state without modifying internal state.

        This method evaluates the plant dynamics for one time step given
        the current state, control inputs, and scenario parameters. It
        returns a new state dictionary WITHOUT modifying the internal
        state, allowing safety systems to evaluate the proposed state
        before committing.

        Args:
            u: Control inputs (setpoints) with keys:
               - SP_F_Reflux: Reflux flow setpoint (t/h)
               - SP_F_Reboil: Reboiler duty setpoint (MW)
               - SP_F_ToTol: Toluene transfer setpoint (t/h)

            scenario: Scenario parameters (disturbances) with keys:
                      - F_feed: Feed flow rate (t/h)
                      - zB_feed: Benzene fraction in feed (mol fraction)
                      - Fouling_Cond: Condenser fouling (0-1)
                      - Fouling_Reb: Reboiler fouling (0-1)

        Returns:
            Dictionary containing the next state (same keys as self.state).
            This is a new dictionary; internal state is not modified.

        Example:
            >>> plant = MyPlant()
            >>> u = {"SP_F_Reflux": 25.0, "SP_F_Reboil": 1.2, "SP_F_ToTol": 55.0}
            >>> scenario = {"F_feed": 80.0, "zB_feed": 0.60,
            ...             "Fouling_Cond": 0.0, "Fouling_Reb": 0.0}
            >>> x_next = plant.step(u, scenario)
            >>> # plant.state is unchanged; x_next contains proposed state
        """
        pass

    @abstractmethod
    def commit(self, x_next: Dict[str, float]) -> None:
        """Accept tentative state and update internal state.

        This method commits a previously computed state (typically from
        `step()`) to become the new internal state. This completes the
        two-phase commit pattern.

        Args:
            x_next: The state to commit (typically from a prior `step()` call).

        Example:
            >>> x_next = plant.step(u, scenario)
            >>> # Evaluate safety, check constraints, etc.
            >>> if safe(x_next):
            ...     plant.commit(x_next)
        """
        pass

    @abstractmethod
    def esd_safe_state(self) -> None:
        """Execute emergency shutdown and move to safe state.

        This method is called when the safety system triggers an ESD
        (Emergency Shutdown) due to critical process conditions. The
        implementation should:

        1. Immediately move manipulated variables to safe values
        2. Update process variables to reflect the safe configuration
        3. Ensure the plant is in a stable, non-hazardous state

        The safe state should be conservative and designed to:
        - Reduce energy input (lower reboiler duty)
        - Reduce separation stress (lower reflux)
        - Reduce column hydraulic load (lower flows)
        - Bring temperatures and pressures to safer levels

        Note:
            This method modifies internal state directly (does not use
            the two-phase commit pattern) because ESD is an immediate
            protective action that cannot be rolled back.

        Example:
            >>> if critical_condition_detected:
            ...     plant.esd_safe_state()
            ...     # Plant is now in safe state
        """
        pass

    def physics_step(
        self, x: Dict[str, float], u: Dict[str, float], sc: Dict[str, float]
    ) -> Dict[str, float]:
        """Compute physics-based state transition.

        This is an optional helper method that concrete implementations
        can provide to separate physics calculations from the public API.
        The default `step()` implementation can delegate to this method.

        Args:
            x: Current state
            u: Control inputs
            sc: Scenario parameters

        Returns:
            Next state

        Note:
            This method is optional. Implementations are free to organize
            their internal calculations differently.
        """
        raise NotImplementedError(
            "physics_step() is an optional helper. "
            "Override step() or provide a physics_step() implementation."
        )
