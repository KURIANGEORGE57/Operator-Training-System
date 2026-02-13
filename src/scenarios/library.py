"""Pre-built training scenarios with progressive difficulty."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class Scenario:
    """A training scenario with operating conditions and metadata."""

    name: str
    description: str
    difficulty: str  # "Beginner", "Intermediate", "Advanced"
    F_feed: float
    zB_feed: float
    Fouling_Cond: float
    Fouling_Reb: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "F_feed": self.F_feed,
            "zB_feed": self.zB_feed,
            "Fouling_Cond": self.Fouling_Cond,
            "Fouling_Reb": self.Fouling_Reb,
        }


SCENARIO_LIBRARY = [
    Scenario(
        name="Normal Operations",
        description="Standard feed conditions. Maintain on-spec production.",
        difficulty="Beginner",
        F_feed=80.0,
        zB_feed=0.60,
        Fouling_Cond=0.0,
        Fouling_Reb=0.0,
    ),
    Scenario(
        name="Rich Feed",
        description="Higher benzene content in feed stream. Watch for flooding.",
        difficulty="Beginner",
        F_feed=80.0,
        zB_feed=0.72,
        Fouling_Cond=0.0,
        Fouling_Reb=0.0,
    ),
    Scenario(
        name="High Throughput",
        description="Increased feed rate. Balance quality against capacity.",
        difficulty="Intermediate",
        F_feed=110.0,
        zB_feed=0.60,
        Fouling_Cond=0.0,
        Fouling_Reb=0.0,
    ),
    Scenario(
        name="Condenser Fouling",
        description="Degraded condenser performance. Temperature will rise.",
        difficulty="Intermediate",
        F_feed=80.0,
        zB_feed=0.60,
        Fouling_Cond=0.40,
        Fouling_Reb=0.0,
    ),
    Scenario(
        name="Reboiler Fouling",
        description="Reduced reboiler efficiency. Harder to maintain purity.",
        difficulty="Intermediate",
        F_feed=80.0,
        zB_feed=0.60,
        Fouling_Cond=0.0,
        Fouling_Reb=0.35,
    ),
    Scenario(
        name="Double Fouling",
        description="Both condenser and reboiler fouled. Manage dP carefully.",
        difficulty="Advanced",
        F_feed=85.0,
        zB_feed=0.58,
        Fouling_Cond=0.30,
        Fouling_Reb=0.30,
    ),
    Scenario(
        name="Storm Mode",
        description="High feed rate with fouling and lean feed. All challenges at once.",
        difficulty="Advanced",
        F_feed=115.0,
        zB_feed=0.48,
        Fouling_Cond=0.45,
        Fouling_Reb=0.40,
    ),
    Scenario(
        name="Custom",
        description="Set your own conditions via the sliders below.",
        difficulty="Custom",
        F_feed=80.0,
        zB_feed=0.60,
        Fouling_Cond=0.0,
        Fouling_Reb=0.0,
    ),
]


def get_scenario(name: str) -> Optional[Scenario]:
    """Look up a scenario by name."""
    for s in SCENARIO_LIBRARY:
        if s.name == name:
            return s
    return None
