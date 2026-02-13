"""Immutable plant state representation."""

from __future__ import annotations

from dataclasses import dataclass, asdict, fields
from typing import Dict


@dataclass(frozen=True)
class PlantState:
    """Snapshot of the benzene column plant state.

    All values are physical quantities - no unitless abstractions.
    """

    xB_sd: float      # Benzene side-draw purity (mol fraction)
    dP_col: float     # Column differential pressure (bar)
    T_top: float      # Overhead temperature (deg C)
    L_Drum: float     # Reflux drum level (0-1)
    L_Bot: float      # Bottoms level (0-1)
    F_Reflux: float   # Reflux flow (t/h)
    F_Reboil: float   # Reboiler duty (MW)
    F_ToTol: float    # Toluene transfer (t/h)

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> PlantState:
        valid_keys = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in valid_keys})
